import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { createPortal } from 'react-dom'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { Download, RefreshCw } from 'lucide-react'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'
import { isDesktop } from './transport'
import { UpdateController } from './UpdateController'
import type { UpdateCheck } from './UpdateController'
import './updates.css'

export function DesktopUpdates({ workspace }: { workspace: ReturnType<typeof useChampionWorkspace> }) {
  const latestWorkspace = useRef(workspace)
  const trigger = useRef<HTMLButtonElement>(null)
  const panel = useRef<HTMLElement>(null)
  latestWorkspace.current = workspace
  const controller = useRef<UpdateController | null>(null)
  if (!controller.current) controller.current = new UpdateController({
    check: () => invoke<UpdateCheck>('desktop_update_check'),
    download: () => invoke<void>('desktop_update_download'),
    install: () => invoke<void>('desktop_update_install'),
  })
  const updates = controller.current
  const state = useSyncExternalStore(updates.subscribe, updates.getSnapshot)
  const desktop = isDesktop()
  const [expanded, setExpanded] = useState(false)
  const [dismissed, setDismissed] = useState(false)
  useEffect(() => {
    if (expanded && !['checking', 'downloading', 'preparing', 'installing'].includes(state.phase)) panel.current?.querySelector<HTMLButtonElement>('button')?.focus()
  }, [expanded, state.phase])
  useEffect(() => {
    if (!desktop) return
    const timer = setTimeout(() => { void updates.check() }, 1500)
    const listener = listen<{ downloaded: number; total?: number }>('desktop-update-progress', ({ payload }) => updates.progress(payload.downloaded, payload.total))
    return () => { clearTimeout(timer); void listener.then((unlisten) => unlisten()) }
  }, [desktop, updates])
  if (!desktop) return null
  const busy = ['checking', 'downloading', 'preparing', 'installing'].includes(state.phase)
  const progress = state.total ? Math.min(100, Math.round(state.downloaded / state.total * 100)) : undefined
  const text = state.phase === 'downloading' ? `Güncelleme indiriliyor${progress === undefined ? '…' : ` · %${progress}`}`
    : state.phase === 'preparing' ? 'Ayarlar kaydediliyor, otomasyon durduruluyor…'
      : state.phase === 'installing' ? 'Güncelleme kuruluyor. Uygulama yeniden açılacak…'
        : state.phase === 'checking' ? 'Güncellemeler kontrol ediliyor…'
          : state.phase === 'error' ? 'Güncelleme tamamlanamadı.'
          : state.enabled === false ? 'Bu geliştirme paketinde güncelleme kullanılamıyor.'
            : state.offer ? `Yeni sürüm hazır: ${state.offer.version}`
              : state.checked ? 'En güncel sürümü kullanıyorsun.' : 'Uygulama güncellemeleri'
  const target = document.getElementById('desktop-update-panel')
  const showPanel = expanded || (Boolean(state.offer) && !dismissed)
  const open = () => {
    setExpanded(true); setDismissed(false)
    if (!state.offer) void updates.check()
  }
  return <>
    <button ref={trigger} className="desktop-update-trigger" aria-label={state.offer ? 'Yeni sürümü göster' : 'Güncellemeleri kontrol et'} title={state.offer ? `Yeni sürüm: ${state.offer.version}` : 'Güncellemeleri kontrol et'} disabled={busy || workspace.closing || workspace.ended} onClick={open}><Download size={17} /><span>{state.offer ? `Yeni sürüm: ${state.offer.version}` : 'Güncellemeleri kontrol et'}</span></button>
    {showPanel && target && createPortal(<section ref={panel} className="desktop-updates" aria-label="Uygulama güncellemesi" aria-busy={busy}>
    <div><strong role="status">{text}</strong>
      {state.offer && <p>Yüklü: {state.offer.current_version} · Yeni: {state.offer.version}. Ayarların korunur; kurulumdan önce otomasyon durdurulur.</p>}
      {state.error && <p role="alert">{state.error}</p>}
      {state.offer?.notes && <details><summary>Sürüm notları</summary><p className="desktop-updates__notes">{state.offer.notes}</p></details>}
    </div>
    <div className="desktop-updates__actions">
      {state.offer && <button className="button button--primary" disabled={busy || workspace.closing || workspace.ended} onClick={() => { void updates.update(() => latestWorkspace.current.prepareUpdate(), () => latestWorkspace.current.cancelUpdate()) }}><span><Download size={14} /></span><span>Güncelle</span></button>}
      <button className="button button--secondary" disabled={busy || workspace.closing || workspace.ended} onClick={() => { void updates.check() }}><span><RefreshCw size={14} /></span><span>{state.phase === 'error' && !state.offer ? 'Tekrar dene' : 'Güncellemeleri kontrol et'}</span></button>
      <button className="button button--secondary" disabled={busy} onClick={() => { setExpanded(false); setDismissed(true); trigger.current?.focus() }}>{state.offer ? 'Daha sonra' : 'Kapat'}</button>
    </div>
  </section>, target)}
  </>
}
