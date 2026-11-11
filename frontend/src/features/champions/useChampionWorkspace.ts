import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react'
import type { ChampionCatalog, PilotApi, Settings, RunePage, SkinOptions } from '../../api/contracts'
import type { RoleKey, Target } from './selection'
import { initialRole } from './selection'
import { SettingsWriter } from '../settings/SettingsWriter'
import { AutomationController } from '../automation/AutomationController'
import { automationIssues, automationPayload, movePick, queues, roleKey, selectChampion, setSpell } from '../automation/config'
import { preset, restorePreset, withPreset, withoutPreset } from '../runes/model'
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
    if (actionGate.current || closing || ended || automation.busy) return
    if (runeEditorDirty) { setActionError('Kaydedilmemiş rün düzenlemeleri var. Önce rün editöründen kaydet veya geri al.'); return }
    actionGate.current = true
    commandEpoch.current++
    setClosing(true)
    setActionError(undefined)
    try {
      if (writer.getSnapshot().draft) await writer.flush()
      await engine.stop()
      if (mounted.current) setEnded(true)
    } catch (error) { if (mounted.current) setActionError(message(error)) }
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
  const saveRunePreset = (id: number, slot: PresetSlot, page: RunePage) => mutateRunes(async () => {
    const validated = await api.validateRune({ ...page, name: page.name.trim() })
    return (config) => withPreset(config, id, slot, validated)
  })
  const deleteRunePreset = (id: number, slot: PresetSlot) => mutateRunes(async () => (config) => withoutPreset(config, id, slot))
  const discardRunePreset = async (id: number, slot: PresetSlot) => {
    const snapshot = writer.getSnapshot()
    if (!snapshot.draft || !snapshot.saved) return
    const restored = restorePreset(snapshot.draft, snapshot.saved, id, slot)
    // A failed save may already have committed. Restore this context through
    // the ordered writer as well; clearing only the form would leave it queued.
    if (JSON.stringify(restored) !== JSON.stringify(snapshot.draft)) {
      await mutateRunes(async () => (config) => restorePreset(config, snapshot.saved!, id, slot))
    }
  }
  const selectRunePreset = (id: number, slot: 0 | PresetSlot) => mutateRunes(async () => {
    if (slot === 0) {
      const recommendation = await api.recommendedRune(id, new AbortController().signal)
      if (!recommendation.page) throw new Error('Bu şampiyon için güncel katalogla uyumlu öneri bulunamadı.')
    } else {
      const page = preset(writer.getSnapshot().draft, id, slot)
      if (!page) throw new Error('Bu preset okunamadı. Önce düzenleyip kaydet.')
      await api.validateRune(page)
    }
    return (config) => {
      const next = structuredClone(config)
      if (slot === 0) delete next.rune_selection[String(id)]
      else next.rune_selection[String(id)] = slot
      return next
    }
  })

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
    runeBusy, runeEditorDirty, setRuneEditorDirty, saveRunePreset, deleteRunePreset, discardRunePreset, selectRunePreset,
    actionError, choose, editSettings, changeSpell, changeSkin, reorder, start, stop, finish, reloadSettings, apply,
    save: () => { void writer.flush().catch(() => {}) }, reset: () => writer.reset(),
    retry: () => { setAttempt((value) => value + 1); void engine.check() } }
}
