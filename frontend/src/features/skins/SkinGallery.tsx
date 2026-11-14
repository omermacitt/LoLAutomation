import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, Check, ChevronRight, Image, LoaderCircle, RefreshCw, Search, Sparkles, X } from 'lucide-react'
import type { PilotApi, SkinOption, SkinOptions } from '../../api/contracts'
import type { useChampionWorkspace } from '../champions/useChampionWorkspace'
import { roles } from '../champions/selection'
import type { RoleKey } from '../champions/selection'
import { ChampionArtwork } from '../../components/ChampionArtwork'
import { RoleIcon } from '../../components/RoleIcon'
import { selectedSkin, skinFamilies } from './model'
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
  const [detailId, setDetailId] = useState<number>()
  const sequence = useRef(-1)
  const heading = useRef<HTMLHeadingElement>(null)
  const cards = useRef(new Map<number, HTMLButtonElement>())
  const returnFocus = useRef<number | undefined>(undefined)
  const champions = w.catalog.data?.all_champions ?? []
  const champion = champions.find((item) => item.id === championId)
  const data = resource.data?.champion_id === championId ? resource.data : undefined
  const current = championId === undefined ? undefined : selectedSkin(w.draft, role, championId)
  const selected = data?.skins.find((skin) => skin.id === current)
  const families = skinFamilies(data)
  const detail = families.find((family) => family.skin.id === detailId)
  const preview = detail
    ? selected && (selected.id === detail.skin.id || selected.parent_skin_id === detail.skin.id) ? selected : detail.skin
    : selected
  const roleName = roles.find((item) => item.key === role)!.name
  const disabled = !w.ready || resource.loading || Boolean(resource.error) || !data
  const nameOf = (skin: SkinOption) => skin.id === championId! * 1000 ? `Varsayılan ${champion?.name ?? ''}` : skin.name
  const query = search.trim().toLocaleLowerCase('tr')
  const matches = families.filter((family) => [family.skin, ...family.chromas]
    .some((skin) => nameOf(skin).toLocaleLowerCase('tr').includes(query)))

  useEffect(() => {
    if (!champions.length || sequence.current === request.sequence) return
    sequence.current = request.sequence
    setChampionId(champions.some((item) => item.id === request.id) ? request.id : champions[0].id)
    setRole(request.role)
    setSearch('')
    setDetailId(undefined)
  }, [request, champions])

  useEffect(() => {
    if (championId === undefined) return
    const controller = new AbortController()
    setResource({ loading: true })
    setSearch('')
    setDetailId(undefined)
    void api.skins(championId, controller.signal).then((result) => {
      if (!controller.signal.aborted && result.champion_id === championId) setResource({ data: result, loading: false })
    }, (error: unknown) => {
      if (!controller.signal.aborted) setResource({ loading: false, error: error instanceof Error ? error.message : 'Kostümler yüklenemedi.' })
    })
    return () => controller.abort()
  }, [api, championId, attempt])

  useEffect(() => {
    if (detail) heading.current?.focus()
    else if (returnFocus.current !== undefined) {
      cards.current.get(returnFocus.current)?.focus()
      returnFocus.current = undefined
    }
  }, [detail?.skin.id])

  const choose = (skin: SkinOption) => {
    if (disabled || !data || championId === undefined) return
    w.changeSkin(role, championId, skin.id, data)
  }
  const back = () => {
    returnFocus.current = detail?.skin.id
    setDetailId(undefined)
  }

  return <section className="skin-gallery" aria-label="Kostüm galerisi">
    <div className="page-heading">
      <div><p className="eyebrow">SAHNE SENİN.</p><h1>Tarzını oyuna taşı<span>.</span></h1>
        <p className="page-heading__description">Kostümünü keşfet, ayrıntısında favori rengini seç.</p></div>
      <button className="button button--secondary" disabled={resource.loading || w.runeBusy} onClick={() => setAttempt((value) => value + 1)}>
        <RefreshCw size={14} /><span>Kostümleri yenile</span></button>
    </div>

    <div className="skin-context">
      {champion && <ChampionArtwork id={champion.id} name={champion.name} small retryKey={attempt} />}
      <label><span>Şampiyon</span><select aria-label="Kostüm şampiyonu" value={championId ?? ''} disabled={!champions.length || w.runeBusy || w.closing || w.preparing}
        onChange={(event) => setChampionId(Number(event.target.value))}>
        <option value="" disabled>Şampiyon seç</option>{champions.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
      </select></label>
      <label><span>Rol</span><select aria-label="Kostüm rolü" value={role} disabled={w.runeBusy || w.closing || w.preparing}
        onChange={(event) => { const next = event.target.value as RoleKey; setDetailId(undefined); setRole(next); w.setRole(next) }}>
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
          {detail && <button className="button button--secondary skin-back" onClick={back}>
            <ArrowLeft size={15} /><span>Kostüm listesine dön</span></button>}
          <div className="skin-hero">
            {preview && <SkinArtwork championId={champion.id} skinId={preview.id} championName={champion.name} retryKey={attempt} eager />}
            <div className="skin-hero__shade" />
            <div className="skin-hero__content"><span className="skin-hero__label"><Sparkles size={13} /><span>{detail ? 'KOSTÜM AYRINTISI' : 'SENİN SEÇİMİN'}</span></span>
              <h2 ref={heading} tabIndex={detail ? -1 : undefined}>{preview ? nameOf(preview) : 'Kayıtlı seçim korunuyor'}</h2>
              <p>{champion.name}<ChevronRight size={12} /><RoleIcon role={role} />{roleName}</p>
              <span className="skin-hero__status"><Check size={13} /><span>{!preview ? 'Yeni bir kostüm seç'
                : preview.id !== current ? 'Önizleme · seçim yapılmadı'
                  : w.saveState.dirty || w.saveState.saving ? 'Kayıt bekleniyor' : 'Seçim hazır'}</span></span>
            </div>
          </div>

          {detail ? <section className="skin-detail" aria-label="Kostüm ayrıntısı">
            <div className="skin-detail__original"><div><h3>{nameOf(detail.skin)}</h3>
              <p>{detail.chromas.length ? 'Kostümü orijinal haliyle kullanabilir veya aşağıdan bir renk paketi seçebilirsin.'
                : 'Bu kostümü seçtiğin rol ve şampiyon için kullanabilirsin.'}</p></div>
              <button className="button button--secondary" disabled={disabled} aria-pressed={current === detail.skin.id}
                onClick={() => choose(detail.skin)}>{detail.chromas.length ? 'Orijinal kostümü kullan' : 'Bu kostümü kullan'}</button></div>
            <h3 className="skin-detail__heading">Renk paketleri <span>{detail.chromas.length}</span></h3>
            {!detail.chromas.length ? <p className="skin-owned-note">Bu kostüm için sahip olduğun bir renk paketi bulunmuyor.</p>
              : <div className="skin-grid chroma-grid">
                {detail.chromas.map((chroma) => <button key={chroma.id} className={`skin-card chroma-card ${current === chroma.id ? 'skin-card--selected' : ''}`}
                  aria-label={`${chroma.name} renk paketini seç`} aria-pressed={current === chroma.id} disabled={disabled} onClick={() => choose(chroma)}>
                  <div className="skin-card__image"><SkinArtwork championId={champion.id} skinId={chroma.id} championName={champion.name} retryKey={attempt} />
                    {current === chroma.id && <span className="skin-card__check"><Check size={16} /></span>}</div>
                  <div className="skin-card__details"><span>RENK PAKETİ</span><strong>{chroma.name}</strong>
                    <small><span>{current === chroma.id ? 'Seçili renk paketi' : 'Bu rengi seç'}</span><ChevronRight size={12} /></small></div>
                </button>)}
              </div>}
          </section> : <>
            <div className="skin-collection-header"><div><p className="eyebrow">KOLEKSİYONUN</p><h3>{champion.name} kostümleri <span>{families.length}</span></h3></div>
              <button className="button button--secondary" disabled={disabled || current === champion.id * 1000}
                onClick={() => choose(data.skins.find((skin) => skin.id === champion.id * 1000)!)}>Varsayılana dön</button></div>
            <div className="skin-collection-tools"><label className="search-field"><Search size={16} />
              <input aria-label="Kostüm ara" placeholder="Kostüm veya renk ara…" value={search} onChange={(event) => setSearch(event.target.value)} />
              {search && <button aria-label="Kostüm aramasını temizle" onClick={() => setSearch('')}><X size={13} /></button>}</label>
              <span>Renk paketleri kostüm ayrıntısında</span></div>
            {families.length === 1 && <p className="skin-owned-note">Bu şampiyon için sahip olduğun ek bir kostüm görünmüyor. Varsayılan kostümü kullanabilirsin.</p>}
            <div className="skin-grid">
              {matches.map(({ skin, chromas }) => {
                const chosen = current === skin.id || selected?.parent_skin_id === skin.id
                return <button key={skin.id} ref={(node) => { if (node) cards.current.set(skin.id, node); else cards.current.delete(skin.id) }}
                  className={`skin-card ${chosen ? 'skin-card--selected' : ''}`} aria-label={`${nameOf(skin)} ayrıntılarını aç`}
                  aria-pressed={chosen} aria-describedby={`skin-summary-${skin.id}`} disabled={disabled} onClick={() => setDetailId(skin.id)}>
                  <div className="skin-card__image"><SkinArtwork championId={champion.id} skinId={skin.id} championName={champion.name} retryKey={attempt} />
                    <span className="skin-card__badge">{skin.id === champion.id * 1000 ? 'VARSAYILAN' : 'KOLEKSİYONUNDA'}</span>
                    {chosen && <span className="skin-card__check"><Check size={16} /></span>}</div>
                  <div className="skin-card__details"><span>{chromas.length ? `${chromas.length} renk paketi` : champion.name}</span><strong>{nameOf(skin)}</strong>
                    <small id={`skin-summary-${skin.id}`}><span>{chosen && selected?.parent_skin_id === skin.id ? `Seçili: ${selected.name}` : chosen ? 'Seçili kostüm' : 'Kostümü incele'}</span><ChevronRight size={12} /></small></div>
                </button>
              })}
            </div>
            {!matches.length && <div className="skin-empty"><Search size={27} /><h3>Kostüm bulunamadı</h3><p>Başka bir isim ara veya aramayı temizle.</p></div>}
          </>}
          <p className="skin-save-note">Kostüm veya renk seçimin otomatik kaydedilir. Oyuna uygulama, otomasyon açıkken şampiyon seçimi sırasında yapılır.</p>
        </>}
  </section>
}
