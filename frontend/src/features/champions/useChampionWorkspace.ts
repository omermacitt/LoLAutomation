import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { ChampionCatalog, PilotApi, Settings, RunePage, SkinOptions } from '../../api/contracts'
import type { RoleKey, Target } from './selection'
import { initialRole } from './selection'
import { SettingsWriter } from '../settings/SettingsWriter'
import { AutomationController } from '../automation/AutomationController'
import { automationIssues, automationPayload, movePick, queues, roleKey, selectChampion, setSpell } from '../automation/config'
import { assignPreset, hasPreset, preset, restorePreset, withPreset, withoutPreset } from '../runes/model'
import type { PresetSlot } from '../runes/model'
import { withSkin } from '../skins/model'

type Resource<T> = { data?: T; loading: boolean; error?: string }
const message = (error: unknown) => error instanceof Error ? error.message : 'İşlem tamamlanamadı.'

export function useChampionWorkspace(api: PilotApi) {
  // These controllers own drafts and queued commands. Fast Refresh may discard
  // memo caches while preserving refs, so their lifetime cannot depend on useMemo.
  const runtime = useRef<{ api: PilotApi; writer: SettingsWriter; engine: AutomationController } | null>(null)
  if (!runtime.current || runtime.current.api !== api) {
    runtime.current = { api, writer: new SettingsWriter(api), engine: new AutomationController(api) }
  }
  const { writer, engine } = runtime.current
  const failedRuneRoles = useRef(new Map<string, RoleKey>())
  const failedRuneDeletes = useRef(new Map<string, Set<RoleKey>>())
  const noteRuneAssignment = (id: number, runeRole: RoleKey) => {
    for (const [context, roles] of failedRuneDeletes.current) if (context.startsWith(`${id}:`)) roles.add(runeRole)
  }
  const saveState = useSyncExternalStore(writer.subscribe, writer.getSnapshot)
  const automation = useSyncExternalStore(engine.subscribe, engine.getSnapshot)
  const [settings, setSettings] = useState<Resource<Settings>>({ loading: true })
  const [catalog, setCatalog] = useState<Resource<ChampionCatalog>>({ loading: true })
  const [role, setRole] = useState<RoleKey>('TOP')
  const [target, setTarget] = useState<Target>({ kind: 'pick', index: 0 })
  const [attempt, setAttempt] = useState(0)
  const [preparing, setPreparing] = useState(false)
  const [closing, setClosing] = useState(false)
  const [ended, setEnded] = useState(false)
  const [actionError, setActionError] = useState<string>()
  const [runeEditorDirty, setRuneEditorDirty] = useState(false)
  const [runeBusy, setRuneBusy] = useState(false)
  const generation = useRef(0)
  const settingsRef = useRef<Settings | undefined>(undefined)
  const commandEpoch = useRef(0)
  const actionGate = useRef(false)
  const updateLease = useRef(false)
  const lastSaved = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; writer.cancelScheduled() }
  }, [writer])

  useEffect(() => {
    if (ended) return
    void engine.check()
    return () => engine.cancelRead()
  }, [engine, ended])

  useEffect(() => {
    if (ended) return
    const timer = setInterval(() => { void engine.check() }, automation.health?.running ? 1_000 : 4_000)
    return () => clearInterval(timer)
  }, [engine, ended, automation.health?.running])

  useEffect(() => {
    if (ended) return
    const current = ++generation.current
    const controller = new AbortController()
    const alive = () => !controller.signal.aborted && generation.current === current
    setCatalog((previous) => ({ ...previous, loading: true, error: undefined }))
    if (!settingsRef.current) {
      setSettings({ loading: true })
      void api.settings(controller.signal).then((data) => {
        if (!alive()) return
        settingsRef.current = data
        writer.initialize(data)
        setSettings({ data, loading: false })
        setRole(initialRole(data))
      }, (error: unknown) => { if (alive()) setSettings({ loading: false, error: message(error) }) })
    }
    void api.champions(controller.signal).then(
      (data) => { if (alive()) setCatalog({ data, loading: false }) },
      (error: unknown) => { if (alive()) setCatalog((previous) => ({ data: previous.data, loading: false, error: message(error) })) },
    )
    return () => controller.abort()
  }, [api, attempt, writer, ended])

  // Only an acknowledged settings write can update the running engine. Initial
  // load does not push anything. The update endpoint cannot start a stopped run.
  useEffect(() => {
    if (saveState.revision === lastSaved.current) return
    // If the first status poll is late, wait before deciding whether this save
    // needs a live update. A manual start/stop/finish owns its own ordering.
    if (!automation.health && !preparing && !closing && !ended && !automation.busy) return
    lastSaved.current = saveState.revision
    if (saveState.saved && catalog.data && !preparing && !closing && !ended
      && automation.busy !== 'starting' && automation.busy !== 'stopping'
      && queues.some((queue) => queue.value === saveState.saved?.queue_name)) {
      engine.update(automationPayload(saveState.saved, catalog.data))
    }
  }, [saveState.revision, saveState.saved, catalog.data, engine, preparing, closing, ended, automation.health, automation.busy])

  const ready = Boolean(settings.data && catalog.data && !catalog.loading && !catalog.error && !ended)
  const editable = ready && !preparing && !closing && !runeBusy
  const choose = useCallback((id: number | null) => {
    if (!editable || !catalog.data || actionGate.current) return
    const allowed = target.kind === 'ban' ? catalog.data.all_champions : catalog.data.pickable_champions
    if (id !== null && !allowed.some((champion) => champion.id === id)) return
    writer.edit((config) => selectChampion(config, role, target, id))
  }, [editable, catalog.data, role, target, writer])

  const editSettings = (patch: Partial<Pick<Settings, 'queue_name' | 'primary_role_name' | 'secondary_role_name'>>) => {
    if (!editable || actionGate.current) return
    writer.edit((config) => {
      const next = { ...config, ...patch }
      if (roleKey(next.primary_role_name) !== null && roleKey(next.primary_role_name) === roleKey(next.secondary_role_name)) {
        if ('primary_role_name' in patch) next.secondary_role_name = 'None'
        else next.primary_role_name = 'None'
      }
      return next
    })
  }
  const changeSpell = (slot: 'spell1Id' | 'spell2Id', spell: number | null) => {
    if (!editable || target.kind !== 'pick' || actionGate.current) return
    const id = saveState.draft?.role_champions_ui[role]?.[target.index]
    if (id == null || !catalog.data?.pickable_champions.some((champion) => champion.id === id)) return
    writer.edit((config) => setSpell(config, role, id, slot, spell))
  }
  const changeSkin = (skinRole: RoleKey, id: number, skinId: number, options: SkinOptions) => {
    if (!editable || actionGate.current || !catalog.data?.all_champions.some((champion) => champion.id === id)) return
    writer.edit((config) => withSkin(config, skinRole, id, skinId, options))
  }
  const reorder = (index: number, step: -1 | 1) => {
    if (!editable || actionGate.current || index + step < 0 || index + step > 2) return
    writer.edit((config) => movePick(config, role, index, step))
    setTarget((current) => current.kind === 'ban' ? current : {
      kind: 'pick', index: current.index === index ? index + step : current.index === index + step ? index : current.index,
    })
  }

  const start = async () => {
    if (!editable || !catalog.data || actionGate.current || !automation.health || automation.busy) return
    if (runeEditorDirty) { setActionError('Önce rün editöründeki düzenlemeleri kaydet veya geri al.'); return }
    const draft = writer.getSnapshot().draft
    if (!draft) return
    const issues = automationIssues(draft, catalog.data)
    if (issues.length) { setActionError(issues.join(' ')); return }
    actionGate.current = true
    const epoch = ++commandEpoch.current
    setPreparing(true)
    setActionError(undefined)
    try {
      const config = await writer.flush()
      if (epoch !== commandEpoch.current || !mounted.current) return
      await engine.start(automationPayload(config, catalog.data))
    } catch (error) { if (mounted.current) setActionError(message(error)) }
    finally { actionGate.current = false; if (mounted.current) setPreparing(false) }
  }
  const stop = async () => {
    commandEpoch.current++
    setActionError(undefined)
    try { await engine.stop() } catch (error) { if (mounted.current) setActionError(message(error)) }
  }
  const finish = async () => {
    if (ended) return true
    if (actionGate.current || closing || automation.busy) return false
    if (runeEditorDirty) { setActionError('Kaydedilmemiş rün düzenlemeleri var. Önce rün editöründen kaydet veya geri al.'); return false }
    actionGate.current = true
    const epoch = ++commandEpoch.current
    setClosing(true)
    setActionError(undefined)
    try {
      if (writer.getSnapshot().draft) await writer.flush()
      if (epoch !== commandEpoch.current) throw new Error('Bağlantı değişti. Yeniden bağlanıp çıkışı tekrar dene.')
      await engine.stop()
      if (epoch !== commandEpoch.current) throw new Error('Bağlantı değişti. Yeniden bağlanıp çıkışı tekrar dene.')
      if (mounted.current) setEnded(true)
      return true
    } catch (error) { if (mounted.current) setActionError(message(error)); return false }
    finally { actionGate.current = false; if (mounted.current) setClosing(false) }
  }
  const reloadSettings = async () => {
    if (saveState.saving || actionGate.current) return
    actionGate.current = true
    setPreparing(true)
    try {
      const data = await api.settings(new AbortController().signal)
      if (!mounted.current) return
      writer.replace(data)
      failedRuneRoles.current.clear()
      failedRuneDeletes.current.clear()
      settingsRef.current = data
      setSettings({ data, loading: false })
      setActionError(undefined)
    } catch (error) { if (mounted.current) setActionError(message(error)) }
    finally { actionGate.current = false; if (mounted.current) setPreparing(false) }
  }

  const apply = async () => {
    if (!editable || !catalog.data || actionGate.current || automation.busy) return
    try { engine.update(automationPayload(await writer.flush(), catalog.data)) }
    catch (error) { if (mounted.current) setActionError(message(error)) }
  }

  const mutateRunes = async (prepare: () => Promise<(config: Settings) => Settings>) => {
    if (!editable || actionGate.current) throw new Error('Ayarlar hazır olduğunda tekrar dene.')
    actionGate.current = true
    setRuneBusy(true)
    try {
      const update = await prepare()
      if (!mounted.current) throw new Error('Rün işlemi tamamlanmadan pencere kapandı.')
      writer.edit(update)
      await writer.flush()
    } finally { actionGate.current = false; if (mounted.current) setRuneBusy(false) }
  }
  const saveRunePreset = async (id: number, slot: PresetSlot, page: RunePage, runeRole: RoleKey) => {
    let edited = false
    try {
      await mutateRunes(async () => {
        const validated = await api.validateRune({ ...page, name: page.name.trim() })
        return (config) => { edited = true; noteRuneAssignment(id, runeRole); return withPreset(config, id, slot, validated, runeRole) }
      })
      failedRuneRoles.current.delete(`${id}:${slot}`)
    } catch (error) { if (edited) failedRuneRoles.current.set(`${id}:${slot}`, runeRole); throw error }
  }
  const deleteRunePreset = async (id: number, slot: PresetSlot) => {
    let edited = false
    const repeatingPendingDelete = failedRuneDeletes.current.has(`${id}:${slot}`) && !hasPreset(writer.getSnapshot().draft, id, slot)
    try {
      await mutateRunes(async () => (config) => { edited = true; return withoutPreset(config, id, slot) })
      failedRuneDeletes.current.delete(`${id}:${slot}`)
    } catch (error) { if (edited && !repeatingPendingDelete) failedRuneDeletes.current.set(`${id}:${slot}`, new Set()); throw error }
  }
  const canDiscardRunePreset = (id: number, slot: PresetSlot) => {
    const snapshot = writer.getSnapshot()
    const raw = (config?: Settings) => (config?.custom_runes[String(id)] as Record<string, unknown> | undefined)?.[String(slot)]
    return snapshot.dirty && JSON.stringify(raw(snapshot.draft)) !== JSON.stringify(raw(snapshot.saved))
  }
  const discardRunePreset = async (id: number, slot: PresetSlot, runeRole: RoleKey) => {
    const originalRole = failedRuneRoles.current.get(`${id}:${slot}`) ?? runeRole
    const preserve = failedRuneDeletes.current.get(`${id}:${slot}`)
    const snapshot = writer.getSnapshot()
    if (!snapshot.draft || !snapshot.saved) return
    const restored = restorePreset(snapshot.draft, snapshot.saved, id, slot, originalRole, preserve)
    // A failed save may already have committed. Restore this context through
    // the ordered writer as well; clearing only the form would leave it queued.
    if (JSON.stringify(restored) !== JSON.stringify(snapshot.draft)) {
      await mutateRunes(async () => (config) => restorePreset(config, snapshot.saved!, id, slot, originalRole, preserve))
    }
    failedRuneRoles.current.delete(`${id}:${slot}`)
    failedRuneDeletes.current.delete(`${id}:${slot}`)
  }
  const selectRunePreset = (id: number, slot: 0 | PresetSlot | null, runeRole: RoleKey) => mutateRunes(async () => {
    if (slot === 0) {
      const recommendation = await api.recommendedRune(id, new AbortController().signal)
      if (!recommendation.page) throw new Error('Bu şampiyon için güncel katalogla uyumlu öneri bulunamadı.')
    } else if (slot !== null) {
      const page = preset(writer.getSnapshot().draft, id, slot)
      if (!page) throw new Error('Bu preset okunamadı. Önce düzenleyip kaydet.')
      await api.validateRune(page)
    }
    return (config) => { noteRuneAssignment(id, runeRole); return assignPreset(config, id, slot, runeRole) }
  })

  const cancelUpdate = () => {
    if (!updateLease.current) return
    updateLease.current = false
    actionGate.current = false
    setClosing(false)
  }
  const prepareUpdate = async () => {
    if (actionGate.current || closing || ended || runeBusy || automation.busy) return false
    if (runeEditorDirty) {
      setActionError('Güncellemeden önce rün düzenlemelerini kaydet veya geri al.')
      return false
    }
    actionGate.current = true
    updateLease.current = true
    setClosing(true)
    setActionError(undefined)
    const epoch = ++commandEpoch.current
    try {
      await writer.flush()
      if (epoch !== commandEpoch.current || !mounted.current) throw new Error('Bağlantı değişti. Güncellemeyi tekrar dene.')
      await engine.stop()
      if (epoch !== commandEpoch.current || !mounted.current) throw new Error('Bağlantı değişti. Güncellemeyi tekrar dene.')
      // Hold the edit/Start gate until installer launch or explicit abort.
      // finish() would set ended and close the native host too early.
      return true
    } catch (error) {
      if (mounted.current) setActionError(message(error))
      cancelUpdate()
      return false
    }
  }
  const suspendConnection = () => { commandEpoch.current++; writer.suspend(); engine.suspendConnection() }
  const resumeConnection = () => { writer.resume(); setAttempt((value) => value + 1); void engine.check() }
  // Used only after explicit confirmation in the native error fallback. React
  // has unmounted App, so render-time busy/dirty flags cannot gate recovery.
  const recoverFinish = async () => {
    const epoch = ++commandEpoch.current
    if (writer.getSnapshot().draft) await writer.flush()
    if (epoch !== commandEpoch.current) throw new Error('Bağlantı değişti. Yeniden bağlanıp çıkışı tekrar dene.')
    await engine.stop()
    if (epoch !== commandEpoch.current) throw new Error('Bağlantı değişti. Yeniden bağlanıp çıkışı tekrar dene.')
  }

  const needsGuard = saveState.dirty || saveState.saving || preparing || closing || runeBusy || runeEditorDirty
    || (!ended && (automation.health?.running === true || Boolean(automation.busy) || !automation.health))
  useEffect(() => {
    if (!needsGuard) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [needsGuard])

  const health = { data: automation.health, loading: automation.checking }
  return { health, settings, catalog, draft: saveState.draft, role, setRole, target, setTarget,
    ready: editable, dirty: saveState.dirty, saveState, automation, preparing, closing, ended,
    portraitRetryKey: attempt,
    runeBusy, runeEditorDirty, setRuneEditorDirty, saveRunePreset, deleteRunePreset, discardRunePreset, selectRunePreset, canDiscardRunePreset,
    actionError, choose, editSettings, changeSpell, changeSkin, reorder, start, stop, finish, recoverFinish, reloadSettings, apply, suspendConnection, resumeConnection, prepareUpdate, cancelUpdate,
    save: () => { void writer.flush().catch(() => {}) }, reset: () => { writer.reset(); failedRuneRoles.current.clear(); failedRuneDeletes.current.clear() },
    retry: () => { setAttempt((value) => value + 1); void engine.check() } }
}
