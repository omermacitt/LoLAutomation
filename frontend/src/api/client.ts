import { z } from 'zod'
import { catalogSchema, healthSchema, settingsSchema, startResultSchema, stopResultSchema, runePageSchema, runeEditorCatalogSchema, runeRecommendationSchema, skinOptionsSchema } from './contracts'
import type { AutomationConfig, PilotApi, Settings, RunePage } from './contracts'
import { desktopAssetUrl, desktopFetch } from '../desktop/transport'
import { itemCatalogSchema, championItemStatsSchema, itemSetCollectionSchema, itemClientStateSchema } from './itemSets'
import type { ItemSetCollection } from './itemSets'

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) { super(message) }
}

export function championPortraitUrl(id: number): string | undefined {
  return Number.isSafeInteger(id) && id > 0 ? desktopAssetUrl(`/champions/${id}/portrait`) : undefined
}

export const runeIconUrl = (id: number) => Number.isSafeInteger(id) && id > 0 ? desktopAssetUrl(`/runes/icons/${id}`) : undefined
export const itemIconUrl = (id: number) => Number.isSafeInteger(id) && id > 0 ? desktopAssetUrl(`/item-builder/items/${id}/icon`) : undefined
export const skinArtworkUrl = (championId: number, skinId: number) => Number.isSafeInteger(championId) && championId > 0
  && Number.isSafeInteger(skinId) && Math.floor(skinId / 1000) === championId ? desktopAssetUrl(`/champions/${championId}/skins/${skinId}/artwork`) : undefined

export const sameSettings = (a: Settings, b: Settings) => stableJson(a) === stableJson(b)
function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`).join(',')}}`
  return JSON.stringify(value)
}

export class ApiClient implements PilotApi {
  private revision?: string
  private session?: string
  private uncertain?: { config: Settings; revision: string }
  private itemRevision?: string
  private itemUncertain?: { collection: ItemSetCollection; revision: string }
  constructor(private readonly fetcher: typeof fetch = (...args) => desktopFetch(...args)) {}

  private async request<T>(path: string, schema: z.ZodType<T>, signal: AbortSignal,
    options: { method?: string; body?: unknown; headers?: Record<string, string> } = {}): Promise<{ data: T; revision?: string }> {
    const timeout = new AbortController()
    const cancel = () => timeout.abort()
    signal.addEventListener('abort', cancel, { once: true })
    if (signal.aborted) cancel()
    const timer = setTimeout(cancel, 20_000)
    try {
      const response = await this.fetcher(`/api${path}`, {
        signal: timeout.signal, cache: 'no-store', credentials: 'omit',
        ...(options.method ? { method: options.method } : {}),
        ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
        headers: { Accept: 'application/json', ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }), ...options.headers },
      })
      if (!response.ok) {
        const message = response.status === 412
          ? path.startsWith('/item-sets') ? 'Eşya setleri veya bağlı hesap değişti. Taslağın korundu; kayıt durumunu ve istemci bağlantısını yenile.' : 'Ayarlar başka bir pencerede değişti. Yerel seçimlerin korundu; devam etmek için sunucudaki ayarları yükle.'
          : response.status === 503 ? path.startsWith('/item-builder') ? 'Oyun verileri alınamadı. İnternet bağlantını kontrol edip tekrar dene.' : path === '/item-sets' ? 'Yerel eşya setleri okunamadı veya kaydedilemedi. Taslağın korundu.' : 'League istemcisine ulaşılamadı. League’i açıp tekrar dene.'
            : `İşlem tamamlanamadı (${response.status}). Tekrar dene.`
        throw new ApiError(message, response.status)
      }
      const parsed = schema.safeParse(response.status === 204 ? undefined : await response.json())
      if (!parsed.success) throw new ApiError('Gelen veriler okunamadı. Tekrar dene.')
      return { data: parsed.data, revision: response.headers.get('ETag') ?? undefined }
    } catch (error) {
      if (signal.aborted || error instanceof ApiError) throw error
      throw new ApiError(timeout.signal.aborted ? 'Bağlantı zaman aşımına uğradı. Sonuç doğrulanamadı; tekrar dene.' : 'RunePilot servisine ulaşılamadı. İşlem sonucu doğrulanamadı.')
    } finally {
      clearTimeout(timer)
      signal.removeEventListener('abort', cancel)
    }
  }

  private async write<T>(path: string, schema: z.ZodType<T>, method: string, body?: unknown, headers: Record<string, string> = {}) {
    const signal = new AbortController().signal
    if (!this.session) this.session = (await this.request('/session', z.object({ token: z.string().min(20) }), signal)).data.token
    try {
      return await this.request(path, schema, signal, { method, body, headers: { ...headers, 'X-RunePilot-Session': this.session } })
    } catch (error) {
      // Rejected session checks have no side effects. Uncertain mutations are
      // never blindly retried; polling or a settings comparison recovers them.
      if (error instanceof ApiError && error.status === 403) this.session = undefined
      throw error
    }
  }

  health = async (signal: AbortSignal) => (await this.request('/health', healthSchema, signal)).data
  itemCatalog = async (signal: AbortSignal) => (await this.request('/item-builder/catalog', itemCatalogSchema, signal)).data
  itemChampion = async (id: number, signal: AbortSignal) => {
    const data = (await this.request(`/item-builder/champions/${id}`, championItemStatsSchema, signal)).data
    if (data.champion_id !== id) throw new ApiError('Şampiyon istatistikleri eşleşmiyor.')
    return data
  }
  itemSets = async (signal: AbortSignal) => {
    const result = await this.request('/item-sets', itemSetCollectionSchema, signal)
    if (!result.revision) throw new ApiError('Eşya seti kayıt sürümü alınamadı.')
    this.itemRevision = result.revision
    this.itemUncertain = undefined
    return result.data
  }
  saveItemSets = async (collection: ItemSetCollection) => {
    if (this.itemUncertain) {
      const current = await this.request('/item-sets', itemSetCollectionSchema, new AbortController().signal)
      if (!current.revision) throw new ApiError('Eşya seti kayıt sürümü alınamadı.')
      if (stableJson(current.data) !== stableJson(this.itemUncertain.collection) && current.revision !== this.itemUncertain.revision) throw new ApiError('Eşya setleri başka bir pencerede değişti. Taslağın korundu; kayıt durumunu kontrol et.', 412)
      this.itemRevision = current.revision
      this.itemUncertain = undefined
      if (stableJson(current.data) === stableJson(collection)) return current.data
    }
    if (!this.itemRevision) throw new ApiError('Önce eşya setlerini yükle.')
    const revision = this.itemRevision
    try {
      const result = await this.write('/item-sets', itemSetCollectionSchema, 'PUT', collection, { 'If-Match': revision })
      if (!result.revision) throw new ApiError('Eşya seti kayıt sonucu doğrulanamadı.')
      this.itemRevision = result.revision
      return result.data
    } catch (error) {
      if (!(error instanceof ApiError) || error.status === undefined) this.itemUncertain = { collection: structuredClone(collection), revision }
      throw error
    }
  }
  itemClientState = async (signal: AbortSignal) => (await this.request('/item-sets/client-state', itemClientStateSchema, signal)).data
  exportItemSet = async (uid: string, revision: string) => {
    if (!this.itemRevision) throw new ApiError('Önce kayıtlı eşya setlerini yükle.')
    return (await this.write(`/item-sets/${encodeURIComponent(uid)}/export`, itemClientStateSchema, 'POST', { client_revision: revision }, { 'If-Match': this.itemRevision })).data
  }
  champions = async (signal: AbortSignal) => (await this.request('/champion-catalog', catalogSchema, signal)).data
  settings = async (signal: AbortSignal) => {
    const result = await this.request('/settings', settingsSchema, signal)
    this.revision = result.revision
    this.uncertain = undefined
    return result.data
  }

  saveSettings = async (config: Settings): Promise<Settings> => {
    if (this.uncertain) {
      const current = await this.request('/settings', settingsSchema, new AbortController().signal)
      if (sameSettings(current.data, this.uncertain.config) || current.revision === this.uncertain.revision) {
        this.revision = current.revision
        this.uncertain = undefined
      } else throw new ApiError('Ayarlar başka bir pencerede değişti. Yerel seçimlerin korundu.', 412)
    }
    if (!this.revision) throw new ApiError('Kayıt sürümü alınamadı. Backend’i güncelleyip sayfayı yeniden aç.')
    const revision = this.revision
    try {
      const result = await this.write('/settings', settingsSchema, 'PUT', config, { 'If-Match': revision })
      if (!result.revision) throw new ApiError('Kayıt sonucu doğrulanamadı. Tekrar dene.')
      this.revision = result.revision
      return result.data
    } catch (error) {
      if (!(error instanceof ApiError) || error.status === undefined) this.uncertain = { config: structuredClone(config), revision }
      throw error
    }
  }

  start = async (config: AutomationConfig) => (await this.write('/start_automation', startResultSchema, 'POST', config)).data
  update = async (config: AutomationConfig) => (await this.write('/automation/config', startResultSchema, 'PUT', config)).data
  stop = async () => { await this.write('/stop_automation', stopResultSchema, 'POST') }
  runeCatalog = async (signal: AbortSignal) => (await this.request('/runes/editor-catalog', runeEditorCatalogSchema, signal)).data
  recommendedRune = async (championId: number, role: string, signal: AbortSignal) => {
    const result = (await this.request(`/champions/${championId}/runes/recommended/${role}`, runeRecommendationSchema, signal)).data
    if (result.champion_id !== championId || result.role !== role) throw new ApiError('Rün önerisi bu şampiyon ve rolle eşleşmiyor.')
    return result
  }
  validateRune = async (page: RunePage) => (await this.write('/runes/validate', runePageSchema, 'POST', page)).data
  skins = async (championId: number, signal: AbortSignal) => {
    const result = (await this.request(`/champions/${championId}/skins`, skinOptionsSchema, signal)).data
    if (result.champion_id !== championId) throw new ApiError('Kostüm listesi bu şampiyonla eşleşmiyor.')
    return result
  }

}

export const apiClient = new ApiClient()
