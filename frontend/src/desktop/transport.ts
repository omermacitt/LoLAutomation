import { invoke, isTauri } from '@tauri-apps/api/core'

let generation = 0
export const isDesktop = () => isTauri()
export const setDesktopGeneration = (value: number) => { generation = value }
export const desktopAssetUrl = (path: string) => isDesktop() ? `http://runepilot.localhost${path}` : `/api${path}`

type NativeResponse = { status: number; headers: Record<string, string>; body: string }

/** Abort ignores late native replies; uncertain writes are reconciled by ApiClient. */
export const desktopFetch: typeof fetch = async (input, options) => {
  if (!isDesktop()) return fetch(input, options)
  if (typeof input !== 'string' || !input.startsWith('/api/') || input.includes('?') || input.includes('#')) throw new Error('Geçersiz uygulama isteği.')
  const current = generation
  if (!current) throw new Error('Uygulama bağlantısı hazır değil.')
  if (options?.signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  if (input === '/api/session') return Response.json({ token: `desktop-host-session-${current}-managed` })
  if (options?.body !== undefined && typeof options.body !== 'string') throw new Error('Geçersiz uygulama verisi.')
  const headers = new Headers(options?.headers)
  const pending = invoke<NativeResponse>('desktop_request', { input: {
    method: options?.method ?? 'GET', path: input.slice(4), body: options?.body ?? null,
    if_match: headers.get('If-Match'), generation: current,
  } })
  const response = await new Promise<NativeResponse>((resolve, reject) => {
    const aborted = () => reject(new DOMException('Aborted', 'AbortError'))
    options?.signal?.addEventListener('abort', aborted, { once: true })
    pending.then(resolve, reject).finally(() => options?.signal?.removeEventListener('abort', aborted))
  })
  if (current !== generation) throw new Error('Eski bağlantının yanıtı yok sayıldı.')
  const decoded = atob(response.body)
  const bytes = Uint8Array.from(decoded, (character) => character.charCodeAt(0))
  return new Response(response.status === 204 ? null : bytes, { status: response.status, headers: response.headers })
}
