import { Component } from 'react'
import type { ReactNode } from 'react'

type Props = { children: ReactNode; onReload?: () => void }

export class AppErrorBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  render() {
    if (!this.state.failed) return this.props.children
    return <main className="app-error" role="alert">
      <p className="eyebrow">RUNEPILOT</p>
      <h1>Arayüz görüntülenemedi</h1>
      <p>Sayfayı yeniden yükleyerek devam edebilirsin. Kaydedilmemiş düzenlemeler kaybolabilir; çalışan otomasyon durdurulmaz.</p>
      <button className="button button--primary" onClick={() => {
        if (this.props.onReload) this.props.onReload()
        else window.location.reload()
      }}>Arayüzü yeniden yükle</button>
    </main>
  }
}
