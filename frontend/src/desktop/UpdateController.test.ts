import { describe, expect, it, vi } from 'vitest'
import { UpdateController } from './UpdateController'
import { deferred } from '../test/fixtures'

function setup() {
  const bridge = {
    check: vi.fn().mockResolvedValue({ enabled: true, channel: 'stable', update: { version: '1.0.1', current_version: '1.0.0', notes: 'New version' } }),
    download: vi.fn().mockResolvedValue(undefined), install: vi.fn().mockResolvedValue(undefined),
  }
  const prepare = vi.fn().mockResolvedValue(true); const release = vi.fn()
  return { bridge, prepare, release, controller: new UpdateController(bridge) }
}
describe('complete desktop updates', () => {
  it('checks at startup without downloading, saving or stopping', async () => {
    const s = setup(); await s.controller.check()
    expect(s.controller.getSnapshot().offer?.version).toBe('1.0.1')
    expect(s.bridge.download).not.toHaveBeenCalled(); expect(s.prepare).not.toHaveBeenCalled()
  })
  it('waits for download and signature verification, then final save and Stop, before one installer launch', async () => {
    const s = setup(); await s.controller.check()
    const download = deferred<void>(); const prepare = deferred<boolean>()
    s.bridge.download.mockReturnValueOnce(download.promise); s.prepare.mockReturnValueOnce(prepare.promise)
    const updating = s.controller.update(s.prepare, s.release)
    await s.controller.update(s.prepare, s.release)
    expect(s.prepare).not.toHaveBeenCalled(); expect(s.bridge.install).not.toHaveBeenCalled()
    download.resolve(); await Promise.resolve(); await Promise.resolve()
    expect(s.prepare).toHaveBeenCalledOnce(); expect(s.bridge.install).not.toHaveBeenCalled()
    prepare.resolve(true); await updating
    expect(s.bridge.download).toHaveBeenCalledOnce(); expect(s.bridge.install).toHaveBeenCalledOnce()
    expect(s.release).toHaveBeenCalledOnce()
  })
  it('keeps the existing app when a signature or network download fails and retries verification', async () => {
    const s = setup(); await s.controller.check()
    s.bridge.download.mockRejectedValueOnce(new Error('Signature rejected'))
    await s.controller.update(s.prepare, s.release)
    expect(s.prepare).not.toHaveBeenCalled(); expect(s.bridge.install).not.toHaveBeenCalled()
    expect(s.controller.getSnapshot().error).toBe('Signature rejected')
    await s.controller.update(s.prepare, s.release)
    expect(s.bridge.download).toHaveBeenCalledTimes(2); expect(s.bridge.install).toHaveBeenCalledOnce()
  })
  it('blocks installer launch on dirty rune/save/Stop refusal and rechecks preparation on retry', async () => {
    const s = setup(); await s.controller.check(); s.prepare.mockResolvedValueOnce(false)
    await s.controller.update(s.prepare, s.release)
    expect(s.bridge.install).not.toHaveBeenCalled(); expect(s.release).toHaveBeenCalledOnce()
    await s.controller.update(s.prepare, s.release)
    expect(s.prepare).toHaveBeenCalledTimes(2); expect(s.bridge.install).toHaveBeenCalledOnce()
    expect(s.bridge.download).toHaveBeenCalledOnce()
  })
  it('releases the edit gate after installer launch failure and requires a fresh download', async () => {
    const s = setup(); await s.controller.check(); s.bridge.install.mockRejectedValueOnce(new Error('Cannot launch'))
    await s.controller.update(s.prepare, s.release)
    expect(s.controller.getSnapshot().phase).toBe('error'); expect(s.release).toHaveBeenCalledOnce()
    await s.controller.update(s.prepare, s.release)
    expect(s.bridge.download).toHaveBeenCalledTimes(2)
  })
  it('does not offer or install a package when the feed returns no newer version', async () => {
    const s = setup(); s.bridge.check.mockResolvedValueOnce({ enabled: true, channel: 'stable', update: null })
    await s.controller.check(); await s.controller.update(s.prepare, s.release)
    expect(s.controller.getSnapshot().offer).toBeUndefined(); expect(s.bridge.download).not.toHaveBeenCalled()
  })
})
