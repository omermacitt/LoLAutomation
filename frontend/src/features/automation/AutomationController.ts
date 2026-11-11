import type { AutomationConfig, Health, PilotApi } from '../../api/contracts'

export type AutomationState = { health?: Health; checking: boolean; busy?: 'starting' | 'stopping' | 'updating'; error?: string }
export class AutomationController {
  private state: AutomationState = { checking: true }
  private listeners = new Set<() => void>()
  private tail: Promise<unknown> = Promise.resolve()
  private epoch = 0
  private polling = false
  private pending?: AutomationConfig
  private updateQueued = false
  private stoppedByUser = false
  private read?: AbortController
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  constructor(private readonly api: Pick<PilotApi, 'health' | 'start' | 'update' | 'stop'>) {}
  private publish(patch: Partial<AutomationState>) { this.state = { ...this.state, ...patch }; this.listeners.forEach((listener) => listener()) }
  private enqueue(task: () => Promise<void>) {
    const promise = this.tail.then(task, task)
    this.tail = promise.catch(() => {})
    return promise
  }
  private async confirm(): Promise<Health> { return this.api.health(new AbortController().signal) }
  async check() {
    if (this.polling || this.state.busy) return
    this.polling = true
    const epoch = this.epoch
    const read = new AbortController()
    this.read = read
    try {
      const health = await this.api.health(read.signal)
      if (!read.signal.aborted && epoch === this.epoch) this.publish({ health, checking: false })
    } catch {
      if (!read.signal.aborted && epoch === this.epoch) this.publish({ health: undefined, checking: false })
    } finally { if (this.read === read) this.polling = false }
  }
  cancelRead = () => { this.read?.abort(); this.polling = false }
  clearError = () => this.publish({ error: undefined })
  suspendConnection = () => {
    this.epoch++; this.pending = undefined; this.stoppedByUser = true; this.cancelRead()
    this.publish({ health: undefined, checking: false, busy: undefined })
  }

  start(config: AutomationConfig) {
    if (this.state.busy) return Promise.reject(new Error('Bir işlem zaten sürüyor.'))
    const epoch = ++this.epoch
    this.stoppedByUser = false
    this.publish({ busy: 'starting', error: undefined })
    return this.enqueue(async () => {
      if (epoch !== this.epoch) return
      try {
        await this.api.start(config)
        const health = await this.confirm()
        if (epoch !== this.epoch) return
        this.publish({ health, checking: false })
        if (!health.running) throw new Error('Otomasyon çalışmaya başlamadı. Tekrar dene.')
      } catch (error) {
        if (epoch === this.epoch) this.publish({ health: undefined, checking: false, error: error instanceof Error ? error.message : 'Başlatılamadı.' })
        throw error
      } finally { if (epoch === this.epoch) this.publish({ busy: undefined }) }
    })
  }

  stop() {
    const epoch = ++this.epoch
    this.pending = undefined
    this.stoppedByUser = true
    this.publish({ busy: 'stopping', error: undefined })
    return this.enqueue(async () => {
      if (epoch !== this.epoch) return
      try {
        await this.api.stop()
        const health = await this.confirm()
        if (epoch !== this.epoch) return
        this.publish({ health, checking: false })
        if (health.running) throw new Error('Otomasyonun durduğu doğrulanamadı. Tekrar dene.')
      } catch (error) {
        if (epoch === this.epoch) this.publish({ health: undefined, checking: false, error: error instanceof Error ? error.message : 'Durdurulamadı.' })
        throw error
      } finally { if (epoch === this.epoch) this.publish({ busy: undefined }) }
    })
  }

  update(config: AutomationConfig) {
    if (this.stoppedByUser || !this.state.health?.running || this.state.busy === 'starting' || this.state.busy === 'stopping') return
    this.pending = structuredClone(config)
    if (this.updateQueued) return
    this.updateQueued = true
    const epoch = this.epoch
    void this.enqueue(async () => {
      try {
        while (this.pending && epoch === this.epoch && this.state.health?.running) {
          const payload = this.pending
          this.pending = undefined
          this.publish({ busy: 'updating', error: undefined })
          await this.api.update(payload)
        }
      } catch (error) {
        this.pending = undefined
        if (epoch === this.epoch) {
          this.publish({ health: undefined, error: error instanceof Error ? error.message : 'Çalışan otomasyona uygulanamadı.' })
        }
      } finally {
        this.updateQueued = false
        if (epoch === this.epoch) this.publish({ busy: undefined })
      }
    })
  }
}
