import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { isDesktop, setDesktopGeneration } from './transport'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'
import './desktop.css'

type Status = { phase: 'starting' | 'ready' | 'failed' | 'stopping'; version: string; generation: number; error?: string }
let closeGuard: (() => Promise<boolean>) | undefined
let connectionLost: (() => void) | undefined
let connectionRestored: (() => void) | undefined
let recoveryGuard: (() => Promise<void>) | undefined

export async function recoverDesktopSession() {
  await recoveryGuard?.()
  await invoke('desktop_close')
}

export function useDesktopLifecycle(workspace: ReturnType<typeof useChampionWorkspace>) {
  const latest = useRef(workspace)
  latest.current = workspace
  useEffect(() => {
    if (!isDesktop()) return
    // Retain the guard if an error boundary unmounts App: its writer can still
    // flush an existing draft and confirm Stop before the native host exits.
    closeGuard = () => latest.current.finish()
    connectionLost = () => latest.current.suspendConnection()
    connectionRestored = () => latest.current.resumeConnection()
    recoveryGuard = () => latest.current.recoverFinish()
  }, [])
  useEffect(() => {
    if (isDesktop() && workspace.ended) void invoke('desktop_close').catch(() => {})
  }, [workspace.ended])
}

export function DesktopHost({ children }: { children: ReactNode }) {
  const desktop = isDesktop()
  const [state, setState] = useState<Status>({ phase: 'starting', version: '', generation: 0 })
  const [opened, setOpened] = useState(false)
  const [notice, setNotice] = useState<string>()
  const last = useRef<Status | undefined>(undefined)
  const closing = useRef(false)

  useEffect(() => {
    if (!desktop) return
    let disposed = false
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const next = await invoke<Status>('desktop_status')
        if (disposed) return
        const previous = last.current
        if (previous?.phase === 'ready' && (next.phase !== 'ready' || previous.generation !== next.generation)) {
          setDesktopGeneration(0); connectionLost?.()
        }
        if (next.phase === 'ready' && (previous?.phase !== 'ready' || previous.generation !== next.generation)) {
          setDesktopGeneration(next.generation)
          if (previous) connectionRestored?.()
          setOpened(true)
        }
        last.current = next; setState(next)
      } catch {
        if (!disposed) {
          setDesktopGeneration(0); connectionLost?.()
          const failed: Status = { ...(last.current ?? { version: '', generation: 0 }), phase: 'failed', error: 'Uygulama bağlantısı kurulamadı. Yeniden dene.' }
          last.current = failed; setState(failed)
        }
      } finally { if (!disposed) timer = setTimeout(() => { void poll() }, 800) }
    }
    const closingListener = listen('desktop-close-requested', async () => {
      if (closing.current) return
      closing.current = true
      try {
        if (closeGuard && !await closeGuard()) {
          setNotice('Çıkış tamamlanmadı. Açık rün düzenlemesini kaydet veya geri al; bağlantı ve kayıt hatalarını giderip tekrar kapat.')
          return
        }
        await invoke('desktop_close')
      } catch { setNotice('Uygulama güvenli biçimde kapatılamadı. Bağlantıyı kontrol edip yeniden dene.') }
      finally { closing.current = false }
    })
    void poll()
    return () => { disposed = true; clearTimeout(timer); void closingListener.then((unlisten) => unlisten()) }
  }, [desktop])

  if (!desktop) return children
  return <>
    {notice && <div className="desktop-notice" role="alert"><span>{notice}</span><button onClick={() => setNotice(undefined)}>Anladım</button></div>}
    {opened && <div inert={state.phase !== 'ready'}>{children}</div>}
    {state.phase !== 'ready' && <div className="desktop-startup" role="status"><div className="desktop-startup__card"><span className="desktop-startup__brand">runepilot.</span>
      <h1>{state.phase === 'failed' ? 'Bağlantıyı yeniden kuralım.' : state.phase === 'stopping' ? 'Oturum kapatılıyor…' : 'Oyun planın hazırlanıyor…'}</h1>
      <p>{state.error ?? 'Uygulama birkaç saniye içinde hazır olacak.'}</p>
      {opened && state.phase === 'failed' && <p>Seçimlerin ve açık düzenlemelerin bu pencerede korunuyor. Yeniden bağlanmak otomasyonu başlatmaz.</p>}
      {state.phase === 'failed' && <button className="button button--primary" onClick={() => { setNotice(undefined); void invoke('desktop_restart').catch(() => setNotice('Başlangıç henüz tamamlanmadı. Biraz bekleyip yeniden dene.')) }}>Yeniden bağlan</button>}
      {notice && <p role="alert">{notice}</p>}
      <small>{state.version && `RunePilot ${state.version}`}</small>
    </div></div>}
  </>
}
