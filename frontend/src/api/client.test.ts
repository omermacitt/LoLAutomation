import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient } from './client'
import { catalog, settings } from '../test/fixtures'
import { runePage } from '../test/runeFixtures'

afterEach(() => vi.useRealTimers())

describe('local API client', () => {
  it('requests the exact role and rejects another champion, role or map in a successful reply', async () => {
    const reply = { champion_id: 106, role: 'JUNGLE', map_id: 11, source: 'league', page: runePage, options: [runePage], unavailableReason: null }
    const fetcher = vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json(reply))
      .mockResolvedValueOnce(Response.json({ ...reply, role: 'TOP' }))
      .mockResolvedValueOnce(Response.json({ ...reply, champion_id: 1 }))
      .mockResolvedValueOnce(Response.json({ ...reply, map_id: 12 }))
      .mockResolvedValueOnce(Response.json({ ...reply, options: [] }))
    const api = new ApiClient(fetcher)
    const signal = new AbortController().signal
    expect(await api.recommendedRune(106, 'JUNGLE', signal)).toEqual(reply)
    expect(fetcher.mock.calls[0][0]).toBe('/api/champions/106/runes/recommended/JUNGLE')
    for (let attempt = 0; attempt < 4; attempt++) await expect(api.recommendedRune(106, 'JUNGLE', signal)).rejects.toThrow()
  })
  it('uses the same-origin proxy and validates current backend settings', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(settings))
    const result = await new ApiClient(fetcher).settings(new AbortController().signal)
    expect(result.role_champions_ui.TOP).toEqual([266, 86, 122])
    expect(fetcher).toHaveBeenCalledWith('/api/settings', expect.objectContaining({ credentials: 'omit', cache: 'no-store' }))
    expect(fetcher.mock.calls[0][1]?.method).toBeUndefined()
  })

  it('does not convert malformed settings or an empty champion catalog into defaults', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json({}))
      .mockResolvedValueOnce(Response.json({ all_champions: [], pickable_champions: [] }))
    const api = new ApiClient(fetcher)
    await expect(api.settings(new AbortController().signal)).rejects.toThrow('Gelen veriler okunamadı')
    await expect(api.champions(new AbortController().signal)).rejects.toThrow('Gelen veriler okunamadı')
  })

  it('classifies League unavailability without displaying the server body', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json({ detail: 'secret' }, { status: 503 }))
    await expect(new ApiClient(fetcher).champions(new AbortController().signal)).rejects.toThrow('League istemcisine ulaşılamadı')
  })

  it('bounds stalled requests and forwards cancellation', async () => {
    vi.useFakeTimers()
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))
    }))
    const result = new ApiClient(fetcher).champions(new AbortController().signal)
    const rejected = expect(result).rejects.toThrow('Bağlantı zaman aşımına uğradı')
    await vi.advanceTimersByTimeAsync(20_000)
    await rejected
    expect(fetcher.mock.calls[0][1]?.signal?.aborted).toBe(true)
  })

  it('accepts the champion wire contract', async () => {
    const api = new ApiClient(vi.fn<typeof fetch>().mockResolvedValue(Response.json(catalog)))
    expect(await api.champions(new AbortController().signal)).toEqual(catalog)
  })

  it('requires a loaded revision and uses the current ETag plus session header for saves', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(settings, { headers: { ETag: '"a"' } }))
      .mockResolvedValueOnce(Response.json({ token: 'development-session-token-12345' }))
      .mockResolvedValueOnce(Response.json(settings, { headers: { ETag: '"b"' } }))
      .mockResolvedValueOnce(Response.json(settings, { headers: { ETag: '"c"' } }))
    const client = new ApiClient(fetcher)
    await expect(client.saveSettings(settings)).rejects.toThrow('Kayıt sürümü alınamadı')
    expect(fetcher).not.toHaveBeenCalled()
    await client.settings(new AbortController().signal)
    await client.saveSettings(settings)
    await client.saveSettings(settings)
    expect(fetcher.mock.calls[2][1]).toMatchObject({ method: 'PUT', headers: { 'If-Match': '"a"', 'X-RunePilot-Session': 'development-session-token-12345' } })
    expect(fetcher.mock.calls[3][1]?.headers).toMatchObject({ 'If-Match': '"b"' })
  })

  it('recovers a lost successful PUT response before saving a later edit', async () => {
    const earlier = { ...settings, queue_name: 'Normal Draft' }
    const later = { ...settings, queue_name: 'Ranked Flex' }
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(settings, { headers: { ETag: '"a"' } }))
      .mockResolvedValueOnce(Response.json({ token: 'development-session-token-12345' }))
      .mockRejectedValueOnce(new TypeError('response lost'))
      .mockResolvedValueOnce(Response.json(earlier, { headers: { ETag: '"b"' } }))
      .mockResolvedValueOnce(Response.json(later, { headers: { ETag: '"c"' } }))
    const client = new ApiClient(fetcher)
    await client.settings(new AbortController().signal)
    await expect(client.saveSettings(earlier)).rejects.toThrow('sonucu doğrulanamadı')
    await expect(client.saveSettings(later)).resolves.toEqual(later)
    expect(fetcher.mock.calls[4][1]?.headers).toMatchObject({ 'If-Match': '"b"' })
  })

  it('does not overwrite another writer when recovering an uncertain PUT', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(Response.json(settings, { headers: { ETag: '"a"' } }))
      .mockResolvedValueOnce(Response.json({ token: 'development-session-token-12345' }))
      .mockRejectedValueOnce(new TypeError('lost'))
      .mockResolvedValueOnce(Response.json({ ...settings, queue_name: 'other-window' }, { headers: { ETag: '"other"' } }))
    const client = new ApiClient(fetcher)
    await client.settings(new AbortController().signal)
    await expect(client.saveSettings({ ...settings, queue_name: 'Normal Draft' })).rejects.toThrow()
    await expect(client.saveSettings({ ...settings, queue_name: 'Ranked Flex' })).rejects.toMatchObject({ status: 412 })
    expect(fetcher.mock.calls.filter((call) => call[1]?.method === 'PUT')).toHaveLength(1)
  })

})
