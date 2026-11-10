import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '../../api/client'
import type { Settings } from '../../api/contracts'
import { deferred, settings } from '../../test/fixtures'
import { SettingsWriter } from './SettingsWriter'

afterEach(() => vi.useRealTimers())
describe('ordered settings writes', () => {
  it('does not save initial data and coalesces a burst of edits', async () => {
    vi.useFakeTimers()
    const saveSettings = vi.fn(async (config: Settings) => config)
    const writer = new SettingsWriter({ saveSettings })
    writer.initialize(settings)
    await vi.advanceTimersByTimeAsync(1_000)
    expect(saveSettings).not.toHaveBeenCalled()
    writer.edit((config) => ({ ...config, queue_name: 'Normal Draft' }))
    writer.edit((config) => ({ ...config, queue_name: 'Ranked Flex' }))
    await vi.advanceTimersByTimeAsync(499)
    expect(saveSettings).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(saveSettings).toHaveBeenCalledTimes(1)
    expect(saveSettings.mock.calls[0][0].queue_name).toBe('Ranked Flex')
    expect(writer.getSnapshot().dirty).toBe(false)
  })

  it('serializes saves and never erases edits made during an in-flight write', async () => {
    const first = deferred<Settings>()
    const saveSettings = vi.fn<(config: Settings) => Promise<Settings>>()
      .mockImplementationOnce(() => first.promise).mockImplementation(async (config) => config)
    const writer = new SettingsWriter({ saveSettings })
    writer.initialize(settings)
    writer.edit((config) => ({ ...config, queue_name: 'Normal Draft' }))
    const flushed = writer.flush()
    writer.edit((config) => ({ ...config, queue_name: 'Ranked Flex' }))
    const secondFlush = writer.flush()
    expect(saveSettings).toHaveBeenCalledTimes(1)
    first.resolve({ ...settings, queue_name: 'Normal Draft' })
    await Promise.all([flushed, secondFlush])
    expect(saveSettings).toHaveBeenCalledTimes(2)
    expect(writer.getSnapshot().draft?.queue_name).toBe('Ranked Flex')
    expect(writer.getSnapshot().dirty).toBe(false)
  })

  it('retains the latest snapshot on failure, preserves rune/skin data and supports retry', async () => {
    const request = deferred<Settings>()
    const saveSettings = vi.fn<(config: Settings) => Promise<Settings>>().mockImplementationOnce(() => request.promise).mockImplementation(async (config) => config)
    const writer = new SettingsWriter({ saveSettings })
    const original = { ...settings, custom_runes: { '266': { '1': { name: 'keep' } } }, custom_skins: { TOP: { '266': 266001 } } }
    writer.initialize(original)
    writer.edit((config) => ({ ...config, queue_name: 'Normal Draft' }))
    const flush = writer.flush()
    const rejected = expect(flush).rejects.toThrow('disk full')
    writer.edit((config) => ({ ...config, queue_name: 'Ranked Flex' }))
    request.reject(new Error('disk full'))
    await rejected
    expect(writer.getSnapshot().dirty).toBe(true)
    expect(writer.getSnapshot().draft?.queue_name).toBe('Ranked Flex')
    await writer.flush()
    expect(saveSettings.mock.calls[1][0].custom_runes).toEqual(original.custom_runes)
    expect(saveSettings.mock.calls[1][0].custom_skins).toEqual(original.custom_skins)
    expect(original.queue_name).toBe(settings.queue_name)
  })

  it('does not retry a revision conflict until the user replaces the local draft', async () => {
    vi.useFakeTimers()
    const saveSettings = vi.fn().mockRejectedValue(new ApiError('changed elsewhere', 412))
    const writer = new SettingsWriter({ saveSettings })
    writer.initialize(settings)
    writer.edit((config) => ({ ...config, queue_name: 'Ranked Flex' }))
    await expect(writer.flush()).rejects.toThrow('changed elsewhere')
    writer.edit((config) => ({ ...config, primary_role_name: 'Mid' }))
    await vi.advanceTimersByTimeAsync(2_000)
    expect(saveSettings).toHaveBeenCalledTimes(1)
    expect(writer.getSnapshot().conflict).toBe(true)
    writer.reset()
    expect(writer.getSnapshot().dirty).toBe(true)
    writer.replace(settings)
    expect(writer.getSnapshot().conflict).toBe(false)
    expect(writer.getSnapshot().dirty).toBe(false)
  })

  it('persists Undo after a failed reply instead of falsely marking an old snapshot as saved', async () => {
    const saveSettings = vi.fn<(config: Settings) => Promise<Settings>>().mockRejectedValueOnce(new Error('response lost')).mockImplementation(async (config) => config)
    const writer = new SettingsWriter({ saveSettings })
    writer.initialize(settings)
    writer.edit((config) => ({ ...config, queue_name: 'Ranked Flex' }))
    await expect(writer.flush()).rejects.toThrow('response lost')
    writer.reset()
    expect(writer.getSnapshot().dirty).toBe(true)
    await writer.flush()
    expect(saveSettings.mock.calls[1][0].queue_name).toBe(settings.queue_name)
    expect(writer.getSnapshot().dirty).toBe(false)
  })
})
