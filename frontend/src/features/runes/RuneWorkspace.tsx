import { useEffect, useRef, useState } from 'react'
import { Check, Copy, LoaderCircle, RefreshCw, Save, Sparkles, Trash2, Undo2 } from 'lucide-react'
import type { PilotApi, RuneEditorCatalog, RunePage, RuneRecommendation } from '../../api/contracts'
import type { useChampionWorkspace } from '../champions/useChampionWorkspace'
import { ChampionArtwork } from '../../components/ChampionArtwork'
import { defaultPage, hasPreset, pageIssues, preset, presetSlots, selectedPreset } from './model'
import type { PresetSlot } from './model'
import { RuneTree } from './RuneTree'
import { SectionIcon } from '../../components/SectionIcon'
import './runes.css'

type Resource<T> = { data?: T; loading: boolean; error?: string }
type Props = { workspace: ReturnType<typeof useChampionWorkspace>; api: PilotApi; request: { id?: number; sequence: number } }
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'Rün işlemi tamamlanamadı.'

export function RuneWorkspace({ workspace: w, api, request }: Props) {
  const [catalog, setCatalog] = useState<Resource<RuneEditorCatalog>>({ loading: true })
  const [recommendation, setRecommendation] = useState<Resource<RuneRecommendation>>({ loading: true })
  const [championId, setChampionId] = useState<number | undefined>(request.id)
  const [slot, setSlot] = useState<0 | PresetSlot>(0)
  const [copySlot, setCopySlot] = useState<PresetSlot>(1)
  const [drafts, setDrafts] = useState<Record<string, RunePage>>({})
  const [attempt, setAttempt] = useState(0)
  const [operationError, setOperationError] = useState<string>()
  const requestSequence = useRef(-1)
  const champions = w.catalog.data?.all_champions ?? []
  const champion = champions.find((item) => item.id === championId)
  const stored = w.saveState.saved
  const active = championId === undefined ? 0 : selectedPreset(stored, championId)
  const key = `${championId}:${slot}`
  const savedPage = championId !== undefined && slot !== 0 ? preset(stored, championId, slot) : undefined
  const hasUnreadablePreset = championId !== undefined && slot !== 0 && hasPreset(stored, championId, slot) && !savedPage
  const unreadable = hasUnreadablePreset && !drafts[key]
  const recommendedPage = recommendation.data && recommendation.data.champion_id === championId ? recommendation.data.page ?? undefined : undefined
  const page = slot === 0 ? recommendedPage : drafts[key] ?? savedPage ?? (catalog.data && champion ? defaultPage(catalog.data, champion.name) : undefined)
  const loading = catalog.loading
  const disabled = !w.ready || w.runeBusy || loading || Boolean(catalog.error)
  const issues = page && catalog.data ? pageIssues(page, catalog.data) : []

  useEffect(() => {
    if (!champions.length || requestSequence.current === request.sequence) return
    requestSequence.current = request.sequence
    const id = champions.some((item) => item.id === request.id) ? request.id : champions[0].id
    setChampionId(id)
    setSlot(selectedPreset(w.saveState.saved, id! ) as 0 | PresetSlot)
  }, [request, champions, w.saveState.saved])

  useEffect(() => {
    const controller = new AbortController()
    setCatalog((previous) => ({ ...previous, loading: true, error: undefined }))
    void api.runeCatalog(controller.signal).then((data) => {
      if (!controller.signal.aborted) setCatalog({ data, loading: false })
    }, (error: unknown) => { if (!controller.signal.aborted) setCatalog((previous) => ({ data: previous.data, loading: false, error: errorMessage(error) })) })
    return () => controller.abort()
  }, [api, attempt])

  useEffect(() => {
    if (championId === undefined) return
    const controller = new AbortController()
    setRecommendation({ loading: true })
    void api.recommendedRune(championId, controller.signal).then((data) => {
      if (!controller.signal.aborted && data.champion_id === championId) setRecommendation({ data, loading: false })
    }, (error: unknown) => { if (!controller.signal.aborted) setRecommendation({ loading: false, error: errorMessage(error) }) })
    return () => controller.abort()
  }, [api, championId, attempt])

  useEffect(() => { w.setRuneEditorDirty(Object.keys(drafts).length > 0) }, [drafts, w.setRuneEditorDirty])

  useEffect(() => {
    const next = { ...drafts }
    let changed = false
    for (const [context, draft] of Object.entries(drafts)) {
      const [id, value] = context.split(':').map(Number)
      const saved = preset(stored, id, value as PresetSlot)
      if (saved && saved.name === draft.name && saved.primaryStyleId === draft.primaryStyleId
        && saved.subStyleId === draft.subStyleId && saved.selectedPerkIds.join(',') === draft.selectedPerkIds.join(',')) {
        delete next[context]
        changed = true
      }
    }
    if (changed) setDrafts(next)
  }, [stored, drafts])

  const changeDraft = (next: RunePage) => {
    const baseline = hasUnreadablePreset ? undefined : savedPage ?? (catalog.data && champion ? defaultPage(catalog.data, champion.name) : undefined)
    const changes = { ...drafts }
    if (JSON.stringify(next) === JSON.stringify(baseline)) delete changes[key]
    else changes[key] = next
    setDrafts(changes)
    w.setRuneEditorDirty(Object.keys(changes).length > 0)
    setOperationError(undefined)
  }
  const clearDraft = (clearKey = key) => {
    const next = { ...drafts }
    delete next[clearKey]
    setDrafts(next)
    w.setRuneEditorDirty(Object.keys(next).length > 0)
  }
  const run = async (operation: () => Promise<void>, clear = false) => {
    const context = key
    setOperationError(undefined)
    try { await operation(); if (clear) clearDraft(context) }
    catch (error) { setOperationError(errorMessage(error)) }
  }
  const copyRecommendation = () => {
    if (!recommendedPage || championId === undefined) return
    const target = `${championId}:${copySlot}`
    if (drafts[target]) { setOperationError('Hedef presette kaydedilmemiş bir düzenleme var. Önce kaydet veya geri al.'); return }
    setDrafts({ ...drafts, [target]: { ...structuredClone(recommendedPage), name: `Custom ${champion?.name ?? ''}`.slice(0, 16) } })
    w.setRuneEditorDirty(true)
    setSlot(copySlot)
  }

  return <section className="rune-workspace" aria-label="Rün çalışma alanı">
    <div className="page-heading"><div><p className="eyebrow">OYUN TARZINA YER AÇ.</p><h1>Her seçimde bir fark<span>.</span></h1><p className="page-heading__description">Rünlerini şekillendir. Her şampiyon için üç farklı plan oluştur.</p></div><button className="button button--secondary" disabled={loading || w.runeBusy} onClick={() => setAttempt((value) => value + 1)}><RefreshCw size={14} /><span>Rünleri yenile</span></button></div>
    <div className="rune-controls">
    <div className="rune-context">{champion && <ChampionArtwork id={champion.id} name={champion.name} small retryKey={w.portraitRetryKey} />}<label><span>Şampiyon</span><select aria-label="Rün şampiyonu" title="Presetler bu şampiyon için tüm rollerde ortaktır." value={championId ?? ''} disabled={w.runeBusy || !champions.length} onChange={(event) => { const id = Number(event.target.value); setChampionId(id); setSlot(selectedPreset(stored, id) as 0 | PresetSlot); setOperationError(undefined) }}><option value="" disabled>Şampiyon seç</option>{champions.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label><span className="rune-active-label"><Check size={13} />{active === 0 ? 'Önerilen' : `Preset ${active}`}</span></div>
    <nav className="rune-preset-tabs" aria-label="Rün presetleri">{([0, ...presetSlots] as const).map((value) => <button key={value} aria-label={value === 0 ? 'Önerilen rünler' : `Rün Preset ${value}`} aria-pressed={slot === value} className={slot === value ? 'rune-preset-tab rune-preset-tab--active' : 'rune-preset-tab'} disabled={w.runeBusy} onClick={() => { setSlot(value); setOperationError(undefined) }}>{value === 0 ? <Sparkles size={15} /> : <SectionIcon section="runes" size={16} />}<span>{value === 0 ? 'Önerilen' : `Preset ${value}`}<small>{value === 0 ? 'Veri paketinden' : drafts[`${championId}:${value}`] ? 'Kaydedilmemiş' : championId !== undefined && hasPreset(stored, championId, value) ? 'Kaydedilmiş' : 'Yeni sayfa'}</small></span>{active === value && <Check size={12} />}</button>)}</nav>
    </div>
    {(catalog.error || operationError || (slot === 0 && recommendation.error)) && <div className="error-banner" role="alert"><p>{operationError ?? catalog.error ?? recommendation.error}</p></div>}
    {loading && !catalog.data ? <div className="rune-loading" role="status"><LoaderCircle className="spin" size={25} /><p>Rün ağaçları yükleniyor…</p></div>
      : !champion ? <div className="empty-state"><SectionIcon section="runes" size={30} /><h3>Önce League istemcisine bağlan</h3><p>Şampiyon listesi hazır olduğunda rünlerini düzenleyebilirsin.</p></div>
        : slot === 0 && !page ? <div className="rune-loading"><Sparkles size={28} /><h3>{recommendation.loading ? 'Öneri yükleniyor…' : recommendation.data?.unavailableReason === 'outdated' ? 'Bu öneri güncel katalogla uyuşmuyor' : 'Bu şampiyon için öneri bulunamadı'}</h3><p>Öneriler RunePilot veri paketinden gelir. Kendi sayfanı oluşturmak için bir preset açabilirsin.</p><button className="button button--primary" disabled={!catalog.data} onClick={() => setSlot(1)}>Preset 1 oluştur</button></div>
          : unreadable ? <div className="rune-loading"><h3>Kayıtlı preset bu biçimde okunamıyor</h3><p>Mevcut kayıt korunuyor. Yeni bir sayfa hazırlayıp kaydedebilir veya bu preseti silebilirsin.</p><button className="button button--primary" disabled={disabled || !catalog.data} onClick={() => changeDraft(defaultPage(catalog.data!, champion.name))}>Yeni sayfa hazırla</button></div>
            : page && catalog.data ? <>
              <div className="rune-page-toolbar"><div>{slot === 0 ? <><strong>Önerilen rün sayfası</strong><small>Kaynak: RunePilot veri paketi · Salt okunur önizleme</small></> : <label><span>Preset adı</span><input aria-label="Rün preset adı" value={page.name} maxLength={16} disabled={disabled} onChange={(event) => changeDraft({ ...page, name: event.target.value })} /></label>}</div><span className="rune-selection-count">{issues.length ? 'Seçimleri kontrol et' : '9 / 9 seçim tamam'}</span></div>
              {issues.length > 0 && <div className="error-banner" role="alert"><ul>{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></div>}
              <RuneTree page={page} catalog={catalog.data} disabled={disabled} readOnly={slot === 0} onChange={changeDraft} retryKey={attempt} />
            </> : null}
    <div className="rune-editor-actions">
      {slot === 0 ? <><div className="rune-copy-actions"><select aria-label="Önerinin kopyalanacağı preset" value={copySlot} disabled={disabled || !page} onChange={(event) => setCopySlot(Number(event.target.value) as PresetSlot)}>{presetSlots.map((value) => <option key={value} value={value}>Preset {value}</option>)}</select><button className="button button--secondary" disabled={disabled || !page || issues.length > 0} onClick={copyRecommendation}><Copy size={14} /><span>Düzenlemek için kopyala</span></button></div><button className="button button--primary" disabled={disabled || !page || active === 0 || issues.length > 0} onClick={() => { void run(() => w.selectRunePreset(championId!, 0)) }}><Sparkles size={14} /><span>Önerileni kullan</span></button></>
        : <><button className="button button--danger" disabled={disabled || championId === undefined || !hasPreset(stored, championId, slot)} onClick={() => { void run(() => w.deleteRunePreset(championId!, slot), true) }}><Trash2 size={14} /><span>Preseti sil</span></button><div className="rune-editor-actions__right"><button className="button button--secondary" disabled={disabled || !drafts[key]} onClick={() => { void run(() => w.discardRunePreset(championId!, slot), true) }}><Undo2 size={14} /><span>Düzenlemeyi geri al</span></button><button className="button button--secondary" disabled={disabled || !savedPage || active === slot || Boolean(drafts[key]) || !catalog.data || pageIssues(savedPage, catalog.data).length > 0} onClick={() => { void run(() => w.selectRunePreset(championId!, slot)) }}>Bu preseti kullan</button><button className="button button--primary" disabled={disabled || !page || unreadable || issues.length > 0} onClick={() => { void run(() => w.saveRunePreset(championId!, slot, page!), true) }}><span className="button-icon" aria-hidden="true">{w.runeBusy ? <LoaderCircle className="spin" size={14} /> : <Save size={14} />}</span><span>Preseti kaydet</span></button></div></>}
    </div>
    <p className="rune-save-note">Kaydettiğin preset bu şampiyon için seçilir. Oyuna uygulama, otomasyon açıkken şampiyon seçimi sırasında yapılır.</p>
  </section>
}
