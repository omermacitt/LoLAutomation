export type UpdateOffer = { version: string; current_version: string; notes: string }
export type UpdateCheck = { enabled: boolean; channel: 'stable' | 'beta'; update: UpdateOffer | null }
export type UpdatePhase = 'idle' | 'checking' | 'available' | 'downloading' | 'preparing' | 'installing' | 'error'
export type UpdateState = { phase: UpdatePhase; enabled?: boolean; channel?: string; offer?: UpdateOffer; error?: string; downloaded: number; total?: number; checked?: boolean }
export type UpdateBridge = { check(): Promise<UpdateCheck>; download(): Promise<void>; install(): Promise<void> }

/** Retries never bypass save/Stop or verification of the complete package. */
export class UpdateController {
  private state: UpdateState = { phase: 'idle', downloaded: 0 }
  private listeners = new Set<() => void>()
  private pending = false
  private downloaded = false
  constructor(private readonly bridge: UpdateBridge) {}
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private publish(patch: Partial<UpdateState>) { this.state = { ...this.state, ...patch }; this.listeners.forEach((listener) => listener()) }
  progress = (downloaded: number, total?: number) => {
    if (this.state.phase === 'downloading') this.publish({ downloaded, total })
  }
  async check() {
    if (this.pending) return
    this.pending = true
    this.publish({ phase: 'checking', error: undefined, offer: undefined })
    this.downloaded = false
    try {
      const result = await this.bridge.check()
      this.publish({ phase: result.update ? 'available' : 'idle', enabled: result.enabled, channel: result.channel, offer: result.update ?? undefined, checked: true })
    } catch { this.publish({ phase: 'error', error: 'Güncellemeler kontrol edilemedi. Bağlantını kontrol edip tekrar dene.' }) }
    finally { this.pending = false }
  }
  async update(prepare: () => Promise<boolean>, release: () => void) {
    if (this.pending || !this.state.offer) return
    this.pending = true
    try {
      if (!this.downloaded) {
        this.publish({ phase: 'downloading', error: undefined, downloaded: 0, total: undefined })
        await this.bridge.download()
        this.downloaded = true
      }
      this.publish({ phase: 'preparing', error: undefined })
      if (!await prepare()) throw new Error('Güncelleme başlamadı. Açık rün düzenlemelerini kaydet veya geri al; kayıt ve bağlantı sorunlarını giderip tekrar dene.')
      this.publish({ phase: 'installing' })
      await this.bridge.install()
    } catch (error) {
      if (this.state.phase === 'installing') this.downloaded = false
      this.publish({ phase: 'error', error: error instanceof Error ? error.message : String(error || 'Güncelleme tamamlanamadı. Tekrar dene.') })
    } finally { release(); this.pending = false }
  }
}
