import { Component } from 'react'
import type { ReactNode } from 'react'
import { isDesktop } from '../desktop/transport'
import { recoverDesktopSession } from '../desktop/DesktopHost'

type Props = { children: ReactNode; onReload?: () => void }

export class AppErrorBoundary extends Component<Props, { failed: boolean; confirm: boolean; busy: boolean; error?: string }> {
  state = { failed: false, confirm: false, busy: false, error: undefined as string | undefined }

  static getDerivedStateFromError() { return { failed: true } }

  render() {
    if (!this.state.failed) return this.props.children
    return <main className="app-error" role="alert">
      <p className="eyebrow">RUNEPILOT</p>
      <h1>Arayüz görüntülenemedi</h1>
      {isDesktop() ? <>
        <p>Ayar kaydını tamamlayıp otomasyonu durdurarak uygulamayı kapatabilirsin. Rün editöründe henüz kaydetmediğin form değişiklikleri kaybolabilir.</p>
        {this.state.error && <p role="alert">{this.state.error}</p>}
        {this.state.confirm ? <>
          <p>Kaydedilmemiş form değişikliklerini bırakarak kapatılsın mı?</p>
          <button className="button button--primary" disabled={this.state.busy} onClick={async () => {
            this.setState({ busy: true, error: undefined })
            try { await recoverDesktopSession() }
            catch { this.setState({ busy: false, error: 'Kayıt veya otomasyonun durması doğrulanamadı. Bağlantıyı yeniden kurup tekrar dene; pencere açık tutuldu.' }) }
          }}>{this.state.busy ? 'Kapatılıyor…' : 'Evet, güvenli biçimde kapat'}</button>
          <button className="button" disabled={this.state.busy} onClick={() => this.setState({ confirm: false })}>Vazgeç</button>
        </> : <button className="button button--primary" onClick={() => this.setState({ confirm: true })}>Otomasyonu durdur ve kapat</button>}
      </> : <>
      <p>Sayfayı yeniden yükleyerek devam edebilirsin. Kaydedilmemiş düzenlemeler kaybolabilir; çalışan otomasyon durdurulmaz.</p>
      <button className="button button--primary" onClick={() => {
        if (this.props.onReload) this.props.onReload()
        else window.location.reload()
      }}>Arayüzü yeniden yükle</button>
      </>}
    </main>
  }
}
