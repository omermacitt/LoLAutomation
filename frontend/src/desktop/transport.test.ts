import { afterEach, describe, expect, it, vi } from 'vitest'
import { deferred } from '../test/fixtures'

const native = vi.hoisted(() => ({ invoke: vi.fn(), isTauri: vi.fn(() => true) }))
vi.mock('@tauri-apps/api/core', () => native)
import { desktopAssetUrl, desktopFetch, setDesktopGeneration } from './transport'

afterEach(() => { setDesktopGeneration(0); native.isTauri.mockReturnValue(true) })
describe('desktop transport', () => {
  it('forwards settings revision and decodes JSON without exposing the backend key', async () => {
    setDesktopGeneration(3)
    native.invoke.mockResolvedValue({ status: 200, headers: { etag: 'next' }, body: btoa('{"saved":true}') })
    const response = await desktopFetch('/api/settings', { method: 'PUT', headers: { 'If-Match': 'previous' }, body: '{}' })
    expect(await response.json()).toEqual({ saved: true })
    expect(response.headers.get('etag')).toBe('next')
    expect(native.invoke).toHaveBeenCalledWith('desktop_request', { input: { method: 'PUT', path: '/settings', body: '{}', if_match: 'previous', generation: 3 } })
    expect(desktopAssetUrl('/runes/icons/8005')).toBe('http://runepilot.localhost/runes/icons/8005')
  })

  it('rejects late replies after a reconnect and never repeats the command', async () => {
    const reply = deferred<{ status: number; headers: {}; body: string }>()
    setDesktopGeneration(1); native.invoke.mockReturnValue(reply.promise)
    const request = desktopFetch('/api/start_automation', { method: 'POST', body: '{}' })
    setDesktopGeneration(0); setDesktopGeneration(2)
    reply.resolve({ status: 200, headers: {}, body: btoa('{}') })
    await expect(request).rejects.toThrow('Eski bağlantı')
    expect(native.invoke).toHaveBeenCalledTimes(1)
  })

  it('rejects an unready connection and external addresses before IPC', async () => {
    await expect(desktopFetch('/api/settings')).rejects.toThrow('hazır değil')
    setDesktopGeneration(1)
    await expect(desktopFetch('https://example.com/api/settings')).rejects.toThrow('Geçersiz')
    expect(native.invoke).not.toHaveBeenCalled()
  })

  it('aborts a native read and ignores its eventual completion', async () => {
    const reply = deferred<unknown>()
    setDesktopGeneration(1); native.invoke.mockReturnValue(reply.promise)
    const abort = new AbortController()
    const response = desktopFetch('/api/health', { signal: abort.signal })
    abort.abort()
    await expect(response).rejects.toMatchObject({ name: 'AbortError' })
    reply.resolve({ status: 200, headers: {}, body: btoa('{}') })
  })
})
