import { useEffect, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, Copy, Plus, RefreshCw, Save, Search, ShoppingBag, Trash2, Upload, X } from 'lucide-react'
import type { PilotApi } from '../../api/contracts'
import type { BuilderItem, ChampionItemStats, ItemCatalog, ItemClientState, ItemSet, ItemSetApi, ItemSetCollection, ItemStats } from '../../api/itemSets'
import { itemIconUrl } from '../../api/client'
import { blockSlots, calculateStats, calculationNote, newItemSet, statLabels } from './model'
import './items.css'

type Props = { api: PilotApi; defaultChampion?: number; onDirty: (dirty: boolean) => void }
const errorText = (error: unknown) => error instanceof Error ? error.message : 'İşlem tamamlanamadı.'
const filters: [string, keyof ItemStats | null][] = [['Hepsi', null], ['AD', 'ad'], ['AP', 'ap'], ['Can', 'hp'], ['Zırh', 'armor'], ['Büyü direnci', 'mr'], ['Saldırı hızı', 'attack_speed'], ['Yetenek hızı', 'haste']]
const format = (value: number, key: keyof ItemStats) => value.toLocaleString('tr-TR', { maximumFractionDigits: key === 'attack_speed' ? 3 : 1 })

function ItemImage({ item }: { item: BuilderItem }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [item])
  return failed ? <ShoppingBag aria-hidden="true" size={25} /> : <img src={itemIconUrl(item.id)} alt="" loading="lazy" onError={() => setFailed(true)} />
}

export function ItemWorkspace({ api, defaultChampion, onDirty }: Props) {
  const feature = api.itemCatalog && api.itemChampion && api.itemSets && api.saveItemSets && api.itemClientState && api.exportItemSet ? api as PilotApi & ItemSetApi : undefined
  const [catalog, setCatalog] = useState<ItemCatalog>()
  const [collection, setCollection] = useState<ItemSetCollection>()
  const [draft, setDraft] = useState<ItemSet>()
  const [block, setBlock] = useState(0)
  const [level, setLevel] = useState(1)
  const [championId, setChampionId] = useState<number | undefined>(defaultChampion)
  const [champion, setChampion] = useState<ChampionItemStats>()
  const [statsError, setStatsError] = useState<string>()
  const [client, setClient] = useState<ItemClientState>()
  const [clientError, setClientError] = useState<string>()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<keyof ItemStats | null>(null)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState<string>()
  const [attempt, setAttempt] = useState(0)
  const [statsAttempt, setStatsAttempt] = useState(0)
  const [deletePending, setDeletePending] = useState(false)
  const saved = collection?.sets.find((s) => s.uid === draft?.uid)
  const dirty = Boolean(draft && JSON.stringify(draft) !== JSON.stringify(saved))
  useEffect(() => { onDirty(dirty || busy); return () => onDirty(false) }, [dirty, busy, onDirty])

  useEffect(() => {
    if (!feature) { setLoading(false); setError('Eşya setleri için RunePilot backend’ini güncelle.'); return }
    const controller = new AbortController()
    setLoading(true); setError(undefined)
    void Promise.all([feature.itemCatalog(controller.signal), feature.itemSets(controller.signal)]).then(([data, sets]) => {
      if (controller.signal.aborted) return
      setCatalog(data); setCollection(sets)
      setDraft(sets.sets[0] ? structuredClone(sets.sets[0]) : undefined)
      setBlock(0); setChampionId(sets.sets[0]?.champion_id ?? defaultChampion ?? data.champions[0]?.id)
    }, (e: unknown) => { if (!controller.signal.aborted) setError(errorText(e)) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    void feature.itemClientState(controller.signal).then((value) => { if (!controller.signal.aborted) { setClient(value); setClientError(undefined) } }, () => { if (!controller.signal.aborted) setClientError('LoL’e aktarmak için istemciyi açıp bağlantıyı yenile.') })
    return () => controller.abort()
    // The builder retains its draft across the other navigation tabs.
  }, [api, attempt]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!feature || !catalog || !championId) { setChampion(undefined); return }
    const controller = new AbortController(); setChampion(undefined); setStatsError(undefined)
    void feature.itemChampion(championId, controller.signal).then((value) => {
      if (!controller.signal.aborted && value.champion_id === championId && value.version === catalog.version) setChampion(value)
      else if (!controller.signal.aborted) setStatsError('Şampiyon ve eşya verilerinin sürümü eşleşmiyor. Listeyi yenile.')
    }, (e: unknown) => { if (!controller.signal.aborted) setStatsError(errorText(e)) })
    return () => controller.abort()
  }, [api, catalog, championId, statsAttempt])

  const itemMap = useMemo(() => new Map(catalog?.items.map((item) => [item.id, item])), [catalog])
  const slots = draft ? blockSlots(draft, block) : Array<null>(6).fill(null)
  const equipped = slots.map((id) => id === null ? undefined : itemMap.get(id))
  const unavailable = slots.some((id) => id !== null && !itemMap.has(id))
  const unavailableBlocks = draft?.blocks.filter((b) => b.items.some((i) => !itemMap.has(i.id))) ?? []
  const stats = champion && !unavailable ? calculateStats(champion, level, equipped.filter((item): item is BuilderItem => Boolean(item))) : undefined
  const matches = catalog?.items.filter((item) => item.name.toLocaleLowerCase('tr').includes(search.toLocaleLowerCase('tr').trim()) && (filter === null || item.stats[filter] > 0)) ?? []
  const ready = Boolean(catalog && collection && !loading && !busy)
  const update = (value: ItemSet) => { setDraft(value); setNotice(undefined); setError(undefined); setDeletePending(false) }
  const guard = () => {
    if (busy || loading || dirty) { setError('Önce eşya setini kaydet veya düzenlemeyi geri al.'); return false }
    return true
  }
  const setSlots = (values: (number | null)[]) => {
    if (!draft || !ready) return
    update({ ...draft, blocks: draft.blocks.map((entry, index) => index === block ? { ...entry, slots: values, items: values.filter((id): id is number => id !== null).map((id) => ({ id, count: 1 })) } : entry) })
  }
  const add = (id: number, index?: number) => {
    if (!draft || !itemMap.has(id)) return
    const target = index ?? slots.indexOf(null)
    if (target < 0) { setError('Altı eşya yuvası dolu. Önce bir eşyayı kaldır.'); return }
    const next = [...slots]; next[target] = id; setSlots(next)
  }
  const persist = async (sets: ItemSet[], selected?: ItemSet) => {
    if (!feature || !ready) return
    setBusy(true); setError(undefined); setNotice(undefined)
    try { const result = await feature.saveItemSets({ sets }); setCollection(result); setDraft(selected ? structuredClone(result.sets.find((s) => s.uid === selected.uid)) : undefined); setNotice('Eşya setleri RunePilot’a kaydedildi.'); setDeletePending(false) }
    catch (e) { setError(errorText(e)) }
    finally { setBusy(false) }
  }
  const save = () => {
    if (!draft || !collection) return
    if (!draft.title.trim() || draft.blocks.some((b) => !b.name.trim())) { setError('Set ve bölüm adları boş olamaz.'); return }
    if (unavailableBlocks.length) { setError('Katalogda olmayan eşyaları değiştirip yeniden kaydet.'); return }
    void persist([...collection.sets.filter((s) => s.uid !== draft.uid), draft], draft)
  }
  const refreshClient = async () => {
    if (!feature || busy) return
    setClient(undefined); setClientError(undefined)
    try { setClient(await feature.itemClientState(new AbortController().signal)) }
    catch { setClientError('LoL’e aktarmak için istemciyi açıp bağlantıyı yenile.') }
  }
  const reconcile = async () => {
    if (!feature || !ready) return
    setBusy(true); setError(undefined); setNotice(undefined)
    try {
      const latest = await feature.itemSets(new AbortController().signal)
      setCollection(latest)
      setNotice('Sunucudaki kayıtlar yenilendi; taslağın korundu. Farklıysa Kaydet bu seti taslağınla değiştirir, diğer setler korunur.')
    } catch (e) { setError(errorText(e)) }
    finally { setBusy(false) }
  }
  const exportSet = async () => {
    if (!feature || !draft || !client || dirty || busy) return
    setBusy(true); setError(undefined); setNotice(undefined)
    try { setClient(await feature.exportItemSet(draft.uid, client.revision)); setNotice('Eşya seti LoL istemcisine aktarıldı. Mevcut diğer setler korundu.') }
    catch (e) { setError(`${errorText(e)} İstemci bağlantısını yenilemeden yeniden aktarma.`); setClient(undefined) }
    finally { setBusy(false) }
  }
  return <section className="item-workspace" aria-label="Eşya seti düzenleyicisi">
    <header className="page-heading"><div><p className="eyebrow">DİZİLİMİNİ HAZIRLA.</p><h1>Eşya setleri<span>.</span></h1><p className="page-heading__description">Eşyalarını seç, seviyeye göre etkilerini gör, kendi setini oluştur.</p></div><button className="button button--secondary" disabled={busy || loading} onClick={() => { if (guard()) setAttempt((x) => x + 1) }}><RefreshCw size={15} />Listeyi yenile</button></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    {catalog && unavailableBlocks.length > 0 && <div className="error-banner" role="alert">Bu sette Sihirdar Vadisi için kullanılamayan eşyalar var: {unavailableBlocks.map((b) => `${b.name} (${b.items.filter((i) => !itemMap.has(i.id)).map((i) => i.id).join(', ')})`).join('; ')}. Bu bölümlere geçip eşyaları kaldır veya değiştir. Diğer kayıtlı setlerin korunur.</div>}
    {notice && <div className="success-banner" role="status">{notice}</div>}
    {loading && <p role="status">Eşya kataloğu ve kayıtlı setler yükleniyor…</p>}
    <div className="item-top-controls">
      <label>Kayıtlı set<select aria-label="Kayıtlı eşya seti" value={saved ? draft?.uid : ''} disabled={!ready} onChange={(e) => { if (!guard()) return; const selected = collection?.sets.find((s) => s.uid === e.target.value); setDraft(selected && structuredClone(selected)); setChampionId(selected?.champion_id ?? championId); setBlock(0); setDeletePending(false) }}><option value="">{draft && !saved ? 'Yeni set · kaydedilmedi' : 'Bir set seç'}</option>{collection?.sets.map((s) => <option key={s.uid} value={s.uid}>{s.title}</option>)}</select></label>
      <button className="button button--secondary" disabled={!ready || (collection?.sets.length ?? 0) >= 100} onClick={() => { if (guard()) { setDraft(newItemSet(championId ?? null)); setBlock(0); setNotice(undefined) } }}><Plus size={15} />Yeni set</button>
      <button className="button button--secondary" disabled={!ready || !draft} onClick={() => { if (draft && guard()) { update({ ...structuredClone(draft), uid: `runepilot-${crypto.randomUUID()}`, title: `${draft.title.slice(0, 50)} kopyası` }); setBlock(0) } }}><Copy size={15} />Kopyala</button>
      <span className="item-version">Veri sürümü: {catalog?.version ?? '—'} · Sihirdar Vadisi</span>
    </div>
    {!draft && !loading && <div className="empty-state"><ShoppingBag size={35} /><h3>İlk eşya setini oluştur</h3><p>Yeni set ile başla. Her bölümde farklı bir altılı dizilimin etkisini görebilirsin.</p></div>}
    {draft && <>
      <div className="item-builder-controls">
        <label>Set adı<input aria-label="Eşya seti adı" maxLength={60} value={draft.title} disabled={!ready} onChange={(e) => update({ ...draft, title: e.target.value })} /></label>
        <label>Şampiyon<select aria-label="Eşya seti şampiyonu" value={championId ?? ''} disabled={!ready} onChange={(e) => { const id = Number(e.target.value); setChampionId(id); update({ ...draft, champion_id: id }) }}>{catalog?.champions.map((c) => <option value={c.id} key={c.id}>{c.name}</option>)}</select></label>
        <label className="item-level">Seviye <strong>{level}</strong><input aria-label="Şampiyon seviyesi" type="range" min={1} max={18} step={1} value={level} onChange={(e) => setLevel(Number(e.target.value))} /></label>
      </div>
      <div className="item-builder-layout">
        <section className="item-catalog-panel" aria-label="Eşya kataloğu"><h2>Eşyalar <small>{matches.length}</small></h2><label className="search-field"><Search size={17} /><input aria-label="Eşya ara" placeholder="Eşya ara…" value={search} onChange={(e) => setSearch(e.target.value)} /></label><div className="item-filters" aria-label="Eşya filtreleri">{filters.map(([name, key]) => <button key={name} aria-pressed={filter === key} onClick={() => setFilter(key)}>{name}</button>)}</div><div className="item-catalog-grid">{matches.map((item) => <button key={item.id} disabled={!ready} draggable={ready} onDragStart={(e) => e.dataTransfer.setData('application/x-runepilot-item', String(item.id))} onClick={() => add(item.id)} title={`${item.name} · ${item.price} altın\n${item.description}`} aria-label={`${item.name} ekle`}><ItemImage item={item} /><span>{item.name}</span><small>{item.price} altın</small></button>)}</div>{!matches.length && <p>Aramana uygun eşya bulunamadı.</p>}</section>
        <div className="item-set-editor">
          <section className="item-inventory-panel" aria-label="Aktif bölüm dizilimi"><div className="panel-heading"><h2>{draft.blocks[block]?.name} <small>{slots.filter(Boolean).length}/6</small></h2><span>Hesap yalnız bu bölüm içindir.</span></div>
            <div className="item-inventory">{slots.map((id, index) => <div className="item-slot" key={index} onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); if (!ready) return; const from = e.dataTransfer.getData('application/x-runepilot-slot'); if (from !== '') { const source = Number(from); if (!Number.isInteger(source) || source < 0 || source > 5) return; const next = [...slots]; [next[source], next[index]] = [next[index], next[source]]; setSlots(next) } else add(Number(e.dataTransfer.getData('application/x-runepilot-item')), index) }}>
              <span className="item-slot-number">{index + 1}</span>{id !== null ? <><div draggable={ready} onDragStart={(e) => e.dataTransfer.setData('application/x-runepilot-slot', String(index))}>{itemMap.get(id) ? <ItemImage item={itemMap.get(id)!} /> : <ShoppingBag size={25} />}</div><span className="item-slot-name">{itemMap.get(id)?.name ?? `Bilinmeyen eşya #${id}`}</span><div className="item-slot-actions"><button aria-label={`${index + 1}. eşyayı sola taşı`} disabled={!ready || index === 0} onClick={() => { const next = [...slots]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; setSlots(next) }}>←</button><button aria-label={`${index + 1}. eşyayı kaldır`} disabled={!ready} onClick={() => setSlots(slots.map((value, i) => i === index ? null : value))}><X size={13} /></button><button aria-label={`${index + 1}. eşyayı sağa taşı`} disabled={!ready || index === 5} onClick={() => { const next = [...slots]; [next[index + 1], next[index]] = [next[index], next[index + 1]]; setSlots(next) }}>→</button></div></> : <span className="item-slot-empty">Eşya ekle veya buraya sürükle</span>}</div>)}</div>
          </section>
          <section className="item-block-panel" aria-label="Eşya seti bölümleri"><div className="panel-heading"><h2>Bölümler</h2><button className="button button--secondary" disabled={!ready || draft.blocks.length >= 20} onClick={() => { update({ ...draft, blocks: [...draft.blocks, { name: 'Yeni bölüm', items: [] }] }); setBlock(draft.blocks.length) }}><Plus size={14} />Bölüm ekle</button></div>{draft.blocks.map((entry, index) => <div className={`item-block-row ${index === block ? 'item-block-row--active' : ''}`} key={index}><button className="item-block-select" aria-label={`${entry.name} bölümünü düzenle`} aria-pressed={block === index} onClick={() => setBlock(index)} disabled={!ready}>{entry.items.length} eşya</button><input aria-label={`${index + 1}. bölüm adı`} value={entry.name} maxLength={60} disabled={!ready} onChange={(e) => update({ ...draft, blocks: draft.blocks.map((b, i) => i === index ? { ...b, name: e.target.value } : b) })} /><button aria-label={`${index + 1}. bölümü yukarı taşı`} disabled={!ready || index === 0} onClick={() => { const next = [...draft.blocks]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; update({ ...draft, blocks: next }); setBlock(index - 1) }}><ArrowUp size={15} /></button><button aria-label={`${index + 1}. bölümü aşağı taşı`} disabled={!ready || index === draft.blocks.length - 1} onClick={() => { const next = [...draft.blocks]; [next[index + 1], next[index]] = [next[index], next[index + 1]]; update({ ...draft, blocks: next }); setBlock(index + 1) }}><ArrowDown size={15} /></button><button aria-label={`${entry.name} bölümünü sil`} disabled={!ready || draft.blocks.length <= 1} onClick={() => { update({ ...draft, blocks: draft.blocks.filter((_, i) => i !== index) }); setBlock(Math.max(0, block >= index ? block - 1 : block)) }}><Trash2 size={15} /></button></div>)}</section>
        </div>
        <aside className="item-stats-panel" aria-label="Seviye ve eşya istatistikleri"><h2>Seviye {level}</h2><p>{catalog?.champions.find((c) => c.id === championId)?.name}</p>{statsError && <div role="alert"><p>{statsError}</p><button className="button button--secondary" onClick={() => setStatsAttempt((n) => n + 1)}>Tekrar dene</button></div>}{!stats && !statsError && <p role="status">{unavailable ? 'Eksik eşya verisi var; hesap gösterilemiyor.' : 'Şampiyon değerleri yükleniyor…'}</p>}{stats && <dl>{(Object.keys(statLabels) as (keyof ItemStats)[]).map((key) => <div key={key}><dt>{statLabels[key]}</dt><dd><strong>{format(stats.total[key], key)}</strong><small>{format(stats.base[key], key)} temel + {format(stats.bonus[key], key)} eşya</small></dd></div>)}</dl>}<p className="item-gold">Toplam: {equipped.reduce((sum, item) => sum + (item?.price ?? 0), 0).toLocaleString('tr-TR')} altın</p><p className="item-calculation-note">{calculationNote}</p><small>Şampiyon: CommunityDragon · Eşyalar: Riot Data Dragon</small></aside>
      </div>
      <footer className="item-save-panel"><div><strong>{dirty ? 'Kaydedilmemiş değişiklikler var' : 'Set kaydedildi'}</strong><p>RunePilot’a kaydet; oyun mağazasında kullanmak için ayrıca LoL’e aktar.</p></div><div className="item-save-actions"><button className="button button--secondary" disabled={!ready || !dirty} onClick={() => { setDraft(saved && structuredClone(saved)); setBlock(0); setError(undefined); setChampionId(saved?.champion_id ?? championId) }}>Düzenlemeyi geri al</button><button className="button button--primary" disabled={!ready || !dirty || unavailableBlocks.length > 0} onClick={save}><Save size={15} />Seti kaydet</button><button className="button button--secondary" disabled={!ready || dirty || !saved || !client || unavailableBlocks.length > 0} onClick={() => { void exportSet() }}><Upload size={15} />LoL’e aktar</button><button className="button button--danger" disabled={!ready || !saved || dirty} onClick={() => setDeletePending(true)}><Trash2 size={15} />Seti sil</button></div></footer>
      {deletePending && <div className="item-delete-confirm" role="alert"><p>“{draft.title}” RunePilot’tan silinsin mi? LoL’e aktarılmış kopyası korunur.</p><button className="button button--danger" disabled={!ready} onClick={() => { if (collection) void persist(collection.sets.filter((s) => s.uid !== draft.uid)) }}>Silmeyi onayla</button><button className="button button--secondary" onClick={() => setDeletePending(false)}>Vazgeç</button></div>}
      <div className="item-client-state"><span>{clientError ?? (client ? 'LoL bağlantısı hazır. Hesap veya istemci setleri değişirse aktarım durdurulur.' : 'İstemci bağlantısını yenile.')}</span><button className="button button--secondary" disabled={!ready} onClick={() => { void refreshClient() }}><RefreshCw size={14} />İstemci bağlantısını yenile</button></div>
      {(dirty || error) && <button className="button button--secondary" disabled={!ready} onClick={() => { void reconcile() }}>Kayıt durumunu kontrol et (taslak korunur)</button>}
    </>}
  </section>
}
