import { ApiError, sameSettings } from '../../api/client'
import type { PilotApi, Settings } from '../../api/contracts'

export type SaveState = { draft?: Settings; saved?: Settings; dirty: boolean; saving: boolean; error?: string; conflict: boolean; revision: number }
const copy = (config: Settings) => structuredClone(config)

/** One in-flight PUT; later edits coalesce into the latest immutable snapshot. */
export class SettingsWriter {
  private state: SaveState = { dirty: false, saving: false, conflict: false, revision: 0 }
  private listeners = new Set<() => void>()
  private timer?: ReturnType<typeof setTimeout>
  private inflight?: Promise<void>
  private version = 0
  constructor(private readonly api: Pick<PilotApi, 'saveSettings'>, private readonly debounce = 500) {}
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private publish(patch: Partial<SaveState>) {
    this.state = { ...this.state, ...patch }
    this.listeners.forEach((listener) => listener())
  }
  initialize(config: Settings) {
    if (!this.state.draft) this.replace(config)
  }
  replace(config: Settings) {
    if (this.inflight) throw new Error('Kayıt sürerken ayarlar değiştirilemez.')
    this.cancelScheduled()
    this.version++
    this.publish({ draft: copy(config), saved: copy(config), dirty: false, saving: false, error: undefined, conflict: false })
  }
  edit(update: (config: Settings) => Settings) {
    if (!this.state.draft) return
    const draft = update(copy(this.state.draft))
    if (sameSettings(draft, this.state.draft)) return
    this.version++
    this.publish({ draft, dirty: true, error: this.state.conflict ? this.state.error : undefined })
    this.cancelScheduled()
    if (!this.state.conflict) this.timer = setTimeout(() => { void this.flush().catch(() => {}) }, this.debounce)
  }
  reset() {
    if (!this.state.saved || this.inflight || this.state.conflict) return
    // A failed HTTP reply may still have committed. Persist the undo as a new
    // ordered write instead of merely marking an old local snapshot as saved.
    const saved = copy(this.state.saved)
    this.edit(() => saved)
  }
  cancelScheduled = () => { clearTimeout(this.timer); this.timer = undefined }

  async flush(): Promise<Settings> {
    this.cancelScheduled()
    if (!this.state.draft) throw new Error('Ayarlar henüz yüklenmedi.')
    if (this.state.conflict) throw new Error(this.state.error)
    if (this.inflight) { await this.inflight; return this.flush() }
    if (!this.state.dirty) return copy(this.state.draft)
    const snapshot = copy(this.state.draft)
    const version = this.version
    this.publish({ saving: true, error: undefined })
    this.inflight = (async () => {
      try {
        const saved = await this.api.saveSettings(snapshot)
        const dirty = this.version !== version
        this.publish({ saved: copy(saved), draft: dirty ? this.state.draft : copy(saved), dirty,
          saving: false, error: undefined, revision: this.state.revision + 1 })
      } catch (error) {
        this.cancelScheduled()
        this.publish({ saving: false, dirty: true,
          error: error instanceof Error ? error.message : 'Ayarlar kaydedilemedi.',
          conflict: error instanceof ApiError && error.status === 412 })
        throw error
      }
    })()
    try { await this.inflight } finally { this.inflight = undefined }
    return this.flush()
  }
}
