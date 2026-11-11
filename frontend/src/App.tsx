import { useState } from 'react'
import { ArrowLeft, ArrowRight, BookOpen, Check, ChevronRight,
  CircleHelp, Crosshair, Layers3, LayoutGrid, LoaderCircle, RefreshCw, Search,
  ShieldBan, Sparkles, TriangleAlert, Wifi, WifiOff, X } from 'lucide-react'
import { apiClient } from './api/client'
import type { PilotApi } from './api/contracts'
import { ChampionArtwork } from './components/ChampionArtwork'
import { RoleIcon } from './components/RoleIcon'
import { GameControls } from './components/GameControls'
import { SpellEditor } from './components/SpellEditor'
import { SaveFooter } from './components/SaveFooter'
import { SelectionAlert } from './components/SelectionAlert'
import { PriorityPicks } from './components/PriorityPicks'
import { roles, resolveChampion, siblingPickIndex } from './features/champions/selection'
import { useChampionWorkspace } from './features/champions/useChampionWorkspace'
import { useGridPageSize } from './features/champions/useGridPageSize'
import { RuneWorkspace } from './features/runes/RuneWorkspace'
import { SkinGallery } from './features/skins/SkinGallery'
import type { SkinRequest } from './features/skins/SkinGallery'
import './styles.css'
import { useDesktopLifecycle } from './desktop/DesktopHost'


export default function App({ api = apiClient }: { api?: PilotApi }) {
  const workspace = useChampionWorkspace(api)
  useDesktopLifecycle(workspace)
  const { health, settings, catalog, draft, role, target, ready } = workspace
  const [search, setSearch] = useState('')
  const [pageAnchor, setPageAnchor] = useState(0)
  const { gridRef, columns, pageSize } = useGridPageSize()
  const [ownedOnly, setOwnedOnly] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [section, setSection] = useState<'champions' | 'runes' | 'skins'>('champions')
  const [runesOpened, setRunesOpened] = useState(false)
  const [runeRequest, setRuneRequest] = useState<{ id?: number; sequence: number }>({ sequence: 0 })
  const [skinsOpened, setSkinsOpened] = useState(false)
  const [skinRequest, setSkinRequest] = useState<SkinRequest>({ role: 'TOP', sequence: 0 })
  const selectedRole = roles.find((item) => item.key === role)!
  const pickable = new Set(catalog.data?.pickable_champions.map((champion) => champion.id))
  const source = catalog.data?.all_champions ?? []
  const matches = source.filter((champion) =>
    champion.name.toLocaleLowerCase('tr').includes(search.trim().toLocaleLowerCase('tr'))
    && (!ownedOnly || pickable.has(champion.id)))
  const pages = Math.max(1, Math.ceil(matches.length / pageSize))
  const currentPage = Math.min(Math.floor(pageAnchor / pageSize), pages - 1)
  const visible = matches.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
  const picks = [0, 1, 2].map((index) => draft?.role_champions_ui[role]?.[index] ?? null)
  const ban = draft?.role_bans_ui[role] ?? null
  const activeId = target.kind === 'ban' ? ban : picks[target.index]
  const errors = [...new Set([settings.error, catalog.error].filter((error): error is string => Boolean(error)))]
  const busy = settings.loading || catalog.loading
  const hasCatalog = Boolean(catalog.data)
  const openRunes = (id?: number) => {
    setRunesOpened(true)
    setRuneRequest((previous) => ({ id, sequence: previous.sequence + 1 }))
    setSection('runes')
  }
  const openSkins = (id?: number) => {
    setSkinsOpened(true)
    setSkinRequest((previous) => ({ id, role, sequence: previous.sequence + 1 }))
    setSection('skins')
  }

  return <>
    <SelectionAlert health={workspace.automation.health} onStop={() => { void workspace.stop() }} stopping={workspace.closing || workspace.automation.busy === 'stopping'} />
    <div className="app-shell">
    <a className="skip-link" href="#main">İçeriğe geç</a>
    <aside className="sidebar">
      <a className="brand" href="#main" aria-label="RunePilot ana ekran">
        <span className="brand__mark"><Layers3 size={24} strokeWidth={1.7} /></span>
        <span>rune<span className="brand__light">pilot</span><span className="brand__dot">.</span></span>
      </a>
      <div className="sidebar__section-label">OYUN ALANIN</div>
      <nav className="main-nav" aria-label="Ana menü">
        <button className={`nav-item ${section === 'champions' ? 'nav-item--active' : ''}`} aria-current={section === 'champions' ? 'page' : undefined} aria-label="Şampiyonlar" onClick={() => setSection('champions')}><LayoutGrid size={19} />Şampiyonlar{section === 'champions' && <span className="nav-item__indicator" />}</button>
        <button className={`nav-item ${section === 'runes' ? 'nav-item--active' : ''}`} aria-current={section === 'runes' ? 'page' : undefined} aria-label="Rünler" title={workspace.runeEditorDirty ? 'Kaydedilmemiş rün düzenlemesi var' : 'Rünlerini düzenle'} onClick={() => openRunes(target.kind === 'pick' ? activeId ?? undefined : picks.find((id) => id !== null) ?? undefined)}><BookOpen size={19} />Rünler{workspace.runeEditorDirty && <span className="nav-item__indicator" />}</button>
        <button className={`nav-item ${section === 'skins' ? 'nav-item--active' : ''}`} aria-current={section === 'skins' ? 'page' : undefined} aria-label="Kostümler" onClick={() => openSkins(target.kind === 'pick' ? activeId ?? undefined : picks.find((id) => id !== null) ?? undefined)}><Sparkles size={19} />Kostümler</button>
      </nav>
      <div className="sidebar-note"><span className="sidebar-note__symbol">✦</span><span>Sen oyununa odaklan.<br /><strong>Hazırlık bizde.</strong></span></div>
      <div className="sidebar__bottom">
        <button className="help-button" onClick={() => setHelpOpen(!helpOpen)} aria-expanded={helpOpen} aria-controls="help-text"><CircleHelp size={17} />Bu sürüm hakkında<ChevronRight size={15} /></button>
        {helpOpen && <p className="help-text" id="help-text">Riot Client’ta kendin giriş yapıp League’i aç. Şampiyon, büyü ve kostüm seçimlerin otomatik kaydedilir. Rün presetlerini editörden kaydet. Oyun işlemleri otomasyon açıkken uygulanır. Çıkmadan önce Kaydet ve oturumu bitir düğmesini kullanabilirsin.</p>}
        <div className={`connection ${health.data ? 'connection--online' : ''}`}>
          {health.loading ? <LoaderCircle size={16} className="spin" /> : health.data ? <Wifi size={16} /> : <WifiOff size={16} />}
          <div><strong>{health.loading ? 'Bağlanıyor' : health.data ? 'Servis bağlı' : 'Servis çevrimdışı'}</strong><span>{health.data ? `RunePilot v${health.data.version}` : 'Bağlantı bekleniyor'}</span></div>
          <span className="connection__dot" />
        </div>
      </div>
    </aside>

    <main id="main" className="main-content">
      <header className="topbar"><div className="breadcrumb"><Crosshair size={15} /><span>League of Legends</span><ChevronRight size={13} /><strong>Hazırlık</strong></div><span className="preview-badge"><span />Geliştirme sürümü</span></header>
      <nav className="mobile-section-nav" aria-label="Görünüm"><button aria-label="Şampiyonlar" aria-pressed={section === 'champions'} onClick={() => setSection('champions')}><LayoutGrid size={15} />Şampiyonlar</button><button aria-label="Rünler" aria-pressed={section === 'runes'} onClick={() => openRunes(target.kind === 'pick' ? activeId ?? undefined : picks[0] ?? undefined)}><BookOpen size={15} />Rünler</button><button aria-label="Kostümler" aria-pressed={section === 'skins'} onClick={() => openSkins(target.kind === 'pick' ? activeId ?? undefined : picks[0] ?? undefined)}><Sparkles size={15} />Kostümler</button></nav>
      <div hidden={section !== 'champions'}>
      <section className="page-heading" aria-labelledby="page-title">
        <div><p className="eyebrow">SENİN HAVUZUN. SENİN OYUNUN.</p><h1 id="page-title">Bir adım önde başla<span>.</span></h1><p className="page-heading__description">Şampiyonlarını belirle, seçim sırasını oluştur. Gerisini akışına bırak.</p></div>
        <button className="button button--secondary" onClick={workspace.retry} disabled={busy}><RefreshCw size={15} className={busy ? 'spin' : ''} />Listeyi yenile</button>
      </section>

      <GameControls workspace={workspace} />

      <section className="workspace-header" aria-label="Seçim alanı">
        <div className="section-title"><span className="section-title__icon"><Crosshair size={19} /></span><div><h2>Şampiyon seçimi</h2><p>Her rol için kendi oyun planını oluştur.</p></div></div>
        <div className="automation-state"><span className={health.data?.running ? 'status-dot status-dot--live' : 'status-dot'} />{health.data?.running ? 'Otomasyon çalışıyor' : health.data ? 'Otomasyon beklemede' : 'Durum bilinmiyor'}</div>
      </section>

      <nav className="role-switcher" aria-label="Roller">{roles.map((item) => <button key={item.key} className={`role-button ${role === item.key ? 'role-button--active' : ''}`} aria-pressed={role === item.key} onClick={() => workspace.setRole(item.key)}><RoleIcon role={item.key} /><span>{item.name}</span><span className="role-button__short">{item.short}</span></button>)}</nav>

      {errors.length > 0 && <div className="error-banner" role="alert"><TriangleAlert size={19} /><div><strong>Veriler henüz hazır değil</strong>{errors.map((error) => <p key={error}>{error}</p>)}</div><button className="button button--secondary" disabled={busy} onClick={workspace.retry}>Tekrar dene</button></div>}

      <div className="workspace-grid">
        <section className="catalog-panel" aria-labelledby="catalog-title" aria-busy={catalog.loading}>
          <div className="panel-heading"><h3 id="catalog-title">Şampiyon havuzu <span>{hasCatalog ? source.length : '—'}</span></h3><span className={`mode-label ${target.kind === 'ban' ? 'mode-label--ban' : ''}`}>{target.kind === 'ban' ? <ShieldBan size={13} /> : <Crosshair size={13} />}{target.kind === 'ban' ? 'Yasaklama' : `${target.index + 1}. tercih seçiliyor`}</span></div>
          <div className="catalog-tools"><label className="search-field"><Search size={17} /><input aria-label="Şampiyon ara" placeholder="Şampiyon ara…" value={search} onChange={(event) => { setSearch(event.target.value); setPageAnchor(0) }} />{search && <button aria-label="Aramayı temizle" onClick={() => { setSearch(''); setPageAnchor(0) }}><X size={14} /></button>}<span className="search-hint">ARA</span></label></div>
          <div className="catalog-filter"><button className={!ownedOnly ? 'filter-button filter-button--active' : 'filter-button'} aria-pressed={!ownedOnly} onClick={() => { setOwnedOnly(false); setPageAnchor(0) }}>Tüm şampiyonlar</button><button className={ownedOnly ? 'filter-button filter-button--active' : 'filter-button'} aria-pressed={ownedOnly} onClick={() => { setOwnedOnly(true); setPageAnchor(0) }}>Seçilebilir <span>{catalog.data?.pickable_champions.length ?? '—'}</span></button></div>

          <div ref={gridRef} className={`champion-grid ${!hasCatalog && catalog.loading ? 'skeleton-grid' : ''}`} style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }} aria-label={catalog.loading ? 'Şampiyonlar yükleniyor' : undefined}>
          {!hasCatalog && catalog.loading ? Array.from({ length: pageSize }, (_, index) => <div className="skeleton-card" key={index}><span /><i /></div>)
            : !hasCatalog ? <div className="empty-state"><WifiOff size={30} /><h4>Şampiyonlarını bekliyoruz</h4><p>League istemcisi hazır olduğunda listeyi yenileyerek devam edebilirsin.</p></div>
              : visible.length === 0 ? <div className="empty-state"><Search size={28} /><h4>Şampiyon bulunamadı</h4><p>Başka bir isim ara veya filtreyi değiştir.</p></div>
                : visible.map((champion) => {
                  const chosenSlot = target.kind === 'pick' ? siblingPickIndex(draft, role, target.index, champion.id) : undefined
                  const allowed = target.kind === 'ban' || (pickable.has(champion.id) && chosenSlot === undefined)
                  const unavailableReason = chosenSlot !== undefined ? `${chosenSlot + 1}. tercihte zaten seçili` : 'Bu hesapta şu anda seçilemiyor'
                  const selected = activeId === champion.id
                  return <button key={champion.id} className={`champion-card ${selected ? 'champion-card--selected' : ''} ${!allowed ? 'champion-card--unavailable' : ''}`} aria-label={`${champion.name} ${target.kind === 'ban' ? 'yasakla' : 'seç'}`} aria-pressed={selected} disabled={!ready || !allowed} title={!allowed ? unavailableReason : champion.name} onClick={() => workspace.choose(champion.id)}><span className="champion-card__image"><ChampionArtwork id={champion.id} name={champion.name} retryKey={workspace.portraitRetryKey} />{selected && <span className="champion-card__check"><Check size={12} strokeWidth={3} /></span>}{!allowed && <span className="champion-card__lock">{chosenSlot !== undefined ? `${chosenSlot + 1}. tercihte seçili` : 'Seçilemiyor'}</span>}</span><span className="champion-card__name">{champion.name}</span></button>
                })}
          </div>

          <div className="catalog-footer"><span>{hasCatalog ? `${matches.length} şampiyon · Sayfada ${pageSize}` : 'Liste bekleniyor'}</span><div className="pagination"><button aria-label="Önceki sayfa" disabled={currentPage === 0} onClick={() => setPageAnchor((currentPage - 1) * pageSize)}><ArrowLeft size={14} /></button><span>{currentPage + 1} / {pages}</span><button aria-label="Sonraki sayfa" disabled={currentPage + 1 >= pages} onClick={() => setPageAnchor((currentPage + 1) * pageSize)}><ArrowRight size={14} /></button></div></div>
        </section>

        <aside className="selection-panel" aria-labelledby="selection-title">
          <div className="selection-heading"><span className="eyebrow">OYUN PLANIN</span><h3 id="selection-title"><RoleIcon role={role} />{selectedRole.name}</h3><p>Öncelik sırasına göre seçimlerin.</p></div>
          <PriorityPicks workspace={workspace} />
          <div className="ban-divider"><span /><ShieldBan size={13} /><span /></div>
          <button className={`ban-slot ${target.kind === 'ban' ? 'ban-slot--active' : ''}`} disabled={!ready} aria-pressed={target.kind === 'ban'} aria-label={`Yasaklama: ${resolveChampion(catalog.data, ban)?.name ?? (ban !== null ? `Şampiyon #${ban}` : 'Şampiyon seç')}`} onClick={() => workspace.setTarget({ kind: 'ban' })}><span className="ban-slot__icon">{ban !== null ? <ChampionArtwork id={ban} name={resolveChampion(catalog.data, ban)?.name ?? `Şampiyon #${ban}`} small retryKey={workspace.portraitRetryKey} /> : <ShieldBan size={21} />}</span><span><small>Yasaklanacak şampiyon</small><strong>{resolveChampion(catalog.data, ban)?.name ?? (ban !== null ? `Şampiyon #${ban}` : 'Bir şampiyon belirle')}</strong></span><ChevronRight size={14} /></button>
          <button className="clear-choice" disabled={!ready || activeId === null} onClick={() => workspace.choose(null)}><X size={12} />Etkin seçimi temizle</button>
          <SpellEditor workspace={workspace} />
          {target.kind === 'pick' && <button className="rune-open-button" disabled={!ready || activeId === null} onClick={() => openRunes(activeId ?? undefined)}><BookOpen size={15} /><span>Rünleri düzenle</span><ChevronRight size={14} /></button>}
          {target.kind === 'pick' && <button className="rune-open-button" disabled={!ready || activeId === null} onClick={() => openSkins(activeId ?? undefined)}><Sparkles size={15} /><span>Kostüm seç</span><ChevronRight size={14} /></button>}
          <div className="selection-tip"><Sparkles size={15} /><p>İlk tercihin uygun değilse sıradaki şampiyonun seçilir.</p></div>
        </aside>
      </div>

      </div>
      {runesOpened && <div hidden={section !== 'runes'}><RuneWorkspace workspace={workspace} api={api} request={runeRequest} /></div>}
      {skinsOpened && <div hidden={section !== 'skins'}><SkinGallery workspace={workspace} api={api} request={skinRequest} /></div>}
      {workspace.ended && <div className="success-banner" role="status">Ayarlar kaydedildi ve otomasyon durduruldu. Bu pencereyi kapatabilirsin.</div>}
      {(workspace.actionError || workspace.automation.error) && <div className="error-banner" role="alert"><TriangleAlert size={18} /><p>{workspace.actionError || workspace.automation.error}</p></div>}
      <SaveFooter workspace={workspace} />
      <div className="page-footer"><span>R U N E P I L O T</span><span>İyi bir oyun, iyi bir hazırlıkla başlar.</span></div>
    </main>
  </div></>
}
