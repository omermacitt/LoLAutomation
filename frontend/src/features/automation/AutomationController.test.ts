import { describe, expect, it, vi } from 'vitest'
import { deferred, health, settings, catalog } from '../../test/fixtures'
import type { Health, PilotApi, StartResult } from '../../api/contracts'
import { AutomationController } from './AutomationController'
import { automationPayload } from './config'

const payload = automationPayload(settings, catalog)
const api = () => ({ health: vi.fn<PilotApi['health']>().mockResolvedValue(health),
  start: vi.fn<PilotApi['start']>().mockResolvedValue({ status: 'started', config: payload }),
  update: vi.fn<PilotApi['update']>().mockResolvedValue({ status: 'updated', config: payload }), stop: vi.fn<PilotApi['stop']>().mockResolvedValue(undefined) })

describe('automation ordering', () => {
  it('invalidates queued Start and updates when the native connection changes', async () => {
    const client = api()
    const controller = new AutomationController(client)
    const start = controller.start(payload)
    controller.suspendConnection()
    await start
    await controller.check()
    controller.update(payload)
    expect(client.start).not.toHaveBeenCalled()
    expect(client.update).not.toHaveBeenCalled()
    expect(controller.getSnapshot().busy).toBeUndefined()
  })
  it('ignores a pre-start poll that arrives after a successful start', async () => {
    const pending = deferred<Health>()
    const client = api()
    client.health.mockImplementationOnce(() => pending.promise).mockResolvedValue({ ...health, running: true })
    const controller = new AutomationController(client)
    const poll = controller.check()
    await controller.start(payload)
    pending.resolve(health)
    await poll
    expect(controller.getSnapshot().health?.running).toBe(true)
  })

  it('queues Stop after an in-flight Start and ignores the late start result', async () => {
    const pending = deferred<StartResult>()
    const client = api()
    client.start.mockImplementation(() => pending.promise)
    const controller = new AutomationController(client)
    const start = controller.start(payload)
    await Promise.resolve()
    const stop = controller.stop()
    expect(client.stop).not.toHaveBeenCalled()
    pending.resolve({ status: 'started', config: payload })
    await Promise.all([start, stop])
    expect(client.stop).toHaveBeenCalledTimes(1)
    expect(controller.getSnapshot().health?.running).toBe(false)
  })

  it('discards pending live updates on Stop; updates never call Start', async () => {
    const pending = deferred<StartResult>()
    const client = api()
    client.health.mockResolvedValueOnce({ ...health, running: true }).mockResolvedValue(health)
    client.update.mockImplementationOnce(() => pending.promise)
    const controller = new AutomationController(client)
    await controller.check()
    controller.update(payload)
    await Promise.resolve()
    controller.update({ ...payload, queue_id: 440 })
    const stop = controller.stop()
    pending.resolve({ status: 'updated', config: payload })
    await stop
    expect(client.update).toHaveBeenCalledTimes(1)
    expect(client.start).not.toHaveBeenCalled()
    expect(controller.getSnapshot().health?.running).toBe(false)
  })

  it('recovers a lost Start response through polling without retrying the command', async () => {
    const client = api()
    client.start.mockRejectedValueOnce(new Error('response lost'))
    client.health.mockResolvedValue({ ...health, running: true })
    const controller = new AutomationController(client)
    await expect(controller.start(payload)).rejects.toThrow('response lost')
    expect(controller.getSnapshot().health).toBeUndefined()
    await controller.check()
    expect(controller.getSnapshot().health?.running).toBe(true)
    expect(client.start).toHaveBeenCalledTimes(1)
  })

  it('does not send background updates after an unsuccessful manual Stop', async () => {
    const client = api()
    client.health.mockResolvedValue({ ...health, running: true })
    client.stop.mockRejectedValue(new Error('stop response lost'))
    const controller = new AutomationController(client)
    await controller.check()
    await expect(controller.stop()).rejects.toThrow('stop response lost')
    await controller.check()
    controller.update(payload)
    await Promise.resolve()
    expect(client.update).not.toHaveBeenCalled()
    expect(client.start).not.toHaveBeenCalled()
  })
})
