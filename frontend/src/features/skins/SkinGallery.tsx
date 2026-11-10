import { useEffect, useRef, useState } from 'react'
import { Check, ChevronRight, Image, LoaderCircle, RefreshCw, Search, Sparkles, X } from 'lucide-react'
import type { PilotApi, SkinOption, SkinOptions } from '../../api/contracts'
import type { useChampionWorkspace } from '../champions/useChampionWorkspace'
import { roles } from '../champions/selection'
import type { RoleKey } from '../champions/selection'
import { ChampionArtwork } from '../../components/ChampionArtwork'
import { RoleIcon } from '../../components/RoleIcon'
import { selectedSkin } from './model'
import { SkinArtwork } from './SkinArtwork'
import './skins.css'

export type SkinRequest = { id?: number; role: RoleKey; sequence: number }
type Props = { workspace: ReturnType<typeof useChampionWorkspace>; api: PilotApi; request: SkinRequest }
type Resource = { data?: SkinOptions; loading: boolean; error?: string }

export function SkinGallery({ workspace: w, api, request }: Props) {
  const [championId, setChampionId] = useState<number | undefined>(request.id)
  const [role, setRole] = useState<RoleKey>(request.role)
  const [resource, setResource] = useState<Resource>({ loading: true })
  const [attempt, setAttempt] = useState(0)
  const [search, setSearch] = useState('')
  const sequence = useRef(-1)
  const champions = w.catalog.data?.all_champions ?? []
  const champion = champions.find((item) => item.id === championId)
  const data = resource.data?.champion_id === championId ? resource.data : undefined
  const current = championId === undefined ? undefined : selectedSkin(w.draft, role, championId)
  const selected = data?.skins.find((skin) => skin.id === current)
  const roleName = roles.find((item) => item.key === role)!.name
  const disabled = !w.ready || resource.loading || Boolean(resource.error) || !data
  const nameOf = (skin: SkinOption) => skin.id === championId! * 1000 ? `Varsayılan ${champion?.name ?? ''}` : skin.name
  const matches = data?.skins.filter((skin) => nameOf(skin).toLocaleLowerCase('tr').includes(search.trim().toLocaleLowerCase('tr'))) ?? []

  useEffect(() => {
    if (!champions.length || sequence.current === request.sequence) return
    sequence.current = request.sequence
    setChampionId(champions.some((item) => item.id === request.id) ? request.id : champions[0].id)
    setRole(request.role)
    setSearch('')
  }, [request, champions])

  useEffect(() => {
    if (championId === undefined) return
    const controller = new AbortController()
    setResource({ loading: true })
    setSearch('')
    void api.skins(championId, controller.signal).then((result) => {
      if (!controller.signal.aborted && result.champion_id === championId) setResource({ data: result, loading: false })
    }, (error: unknown) => {
      if (!controller.signal.aborted) setResource({ loading: false, error: error instanceof Error ? error.message : 'Kostümler yüklenemedi.' })
    })
    return () => controller.abort()
  }, [api, championId, attempt])

  const choose = (skin: SkinOption) => {
    if (disabled || !data || championId === undefined) return
    w.changeSkin(role, championId, skin.id, data)
  }

  return <section className="skin-gallery" aria-label="Kostüm galerisi">
    <div className="page-heading">
      <div><p className="eyebrow">SAHNE SENİN.</p><h1>Tarzını oyuna taşı<span>.</span></h1>
        <p className="page-heading__description">Sahip olduğun kostümleri keşfet. Her rol için favorini belirle.</p></div>
      <button className="button button--secondary" disabled={resource.loading || w.runeBusy} onClick={() => setAttempt((value) => value + 1)}>
        <RefreshCw size={14} />Kostümleri yenile</button>
    </div>

    <div className="skin-context">
      {champion && <ChampionArtwork id={champion.id} name={champion.name} small retryKey={attempt} />}
      <label><span>Şampiyon</span><select aria-label="Kostüm şampiyonu" value={championId ?? ''} disabled={!champions.length || w.runeBusy || w.closing || w.preparing}
        onChange={(event) => setChampionId(Number(event.target.value))}>
        <option value="" disabled>Şampiyon seç</option>{champions.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
      </select></label>
      <label><span>Rol</span><select aria-label="Kostüm rolü" value={role} disabled={w.runeBusy || w.closing || w.preparing}
        onChange={(event) => { const next = event.target.value as RoleKey; setRole(next); w.setRole(next) }}>
        {roles.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}
      </select></label>
      <span className="skin-context__note"><RoleIcon role={role} />Seçimin yalnızca bu rol ve şampiyon için saklanır.</span>
    </div>

    {resource.error && <div className="error-banner" role="alert"><p>{resource.error}</p>
      <button className="button button--secondary" onClick={() => setAttempt((value) => value + 1)}>Kostümleri tekrar yükle</button></div>}
    {!champion ? <div className="skin-empty"><Image size={30} /><h3>Şampiyon listesi bekleniyor</h3><p>League istemcisine bağlandıktan sonra kostümlerini görebilirsin.</p></div>
      : resource.loading ? <div className="skin-empty" role="status"><LoaderCircle size={28} className="spin" /><p>Kostümler yükleniyor…</p></div>
        : data && <>
          {!selected && <div className="error-banner" role="alert"><p>Kayıtlı kostüm bu listede bulunmuyor{current !== undefined ? ` (#${current})` : ''}. Mevcut seçim korunuyor; sahip olduğun başka bir kostüm veya varsayılanı seçebilirsin.</p></div>}
          <div className="skin-hero">
            {selected && <SkinArtwork championId={champion.id} skinId={selected.id} championName={champion.name} retryKey={attempt} eager />}
            <div className="skin-hero__shade" />
            <div className="skin-hero__content"><span className="skin-hero__label"><Sparkles size={13} />SENİN SEÇİMİN</span>
              <h2>{selected ? nameOf(selected) : 'Kayıtlı seçim korunuyor'}</h2>
              <p>{champion.name}<ChevronRight size={12} /><RoleIcon role={role} />{roleName}</p>
              <span className="skin-hero__status"><Check size={13} />{!selected ? 'Yeni bir kostüm seç' : w.saveState.dirty || w.saveState.saving ? 'Kayıt bekleniyor' : 'Seçim hazır'}</span>
            </div>
          </div>

          <div className="skin-collection-header"><div><p className="eyebrow">KOLEKSİYONUN</p><h3>{champion.name} kostümleri <span>{data.skins.length}</span></h3></div>
            <button className="button button--secondary" disabled={disabled || current === champion.id * 1000}
              onClick={() => choose(data.skins.find((skin) => skin.id === champion.id * 1000)!)}>Varsayılana dön</button></div>
          <div className="skin-collection-tools"><label className="search-field"><Search size={16} />
            <input aria-label="Kostüm ara" placeholder="Koleksiyonunda ara…" value={search} onChange={(event) => setSearch(event.target.value)} />
            {search && <button aria-label="Kostüm aramasını temizle" onClick={() => setSearch('')}><X size={13} /></button>}</label>
            <span>Varsayılan + sahip olduğun kostümler</span></div>
          {data.skins.length === 1 && <p className="skin-owned-note">Bu şampiyon için sahip olduğun ek bir kostüm görünmüyor. Varsayılan kostümü kullanabilirsin.</p>}
          <div className="skin-grid">
            {matches.map((skin) => <button key={skin.id} className={`skin-card ${current === skin.id ? 'skin-card--selected' : ''}`}
              aria-label={`${nameOf(skin)} kostümünü seç`} aria-pressed={current === skin.id} disabled={disabled} onClick={() => choose(skin)}>
              <div className="skin-card__image"><SkinArtwork championId={champion.id} skinId={skin.id} championName={champion.name} retryKey={attempt} />
                <span className="skin-card__badge">{skin.id === champion.id * 1000 ? 'VARSAYILAN' : 'KOLEKSİYONUNDA'}</span>
                {current === skin.id && <span className="skin-card__check"><Check size={16} /></span>}</div>
              <div className="skin-card__details"><span>{champion.name}</span><strong>{nameOf(skin)}</strong>
                <small>{current === skin.id ? 'Seçili kostüm' : 'Bu rol için seç'}<ChevronRight size={12} /></small></div>
            </button>)}
          </div>
          {!matches.length && <div className="skin-empty"><Search size={27} /><h3>Kostüm bulunamadı</h3><p>Başka bir isim ara veya aramayı temizle.</p></div>}
          <p className="skin-save-note">Kostüm seçimin otomatik kaydedilir. Oyuna uygulama, otomasyon açıkken şampiyon seçimi sırasında yapılır.</p>
        </>}
  </section>
}
