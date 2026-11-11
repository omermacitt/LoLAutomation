import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'
import { deferred } from '../test/fixtures'

const bridge = vi.hoisted(() => ({ invoke: vi.fn(), listen: vi.fn(), close: undefined as (() => Promise<void>) | undefined }))
vi.mock('@tauri-apps/api/core', () => ({ invoke: bridge.invoke, isTauri: () => true }))
vi.mock('@tauri-apps/api/event', () => ({ listen: bridge.listen }))
import { DesktopHost, recoverDesktopSession, useDesktopLifecycle } from './DesktopHost'
import { AppErrorBoundary } from '../components/AppErrorBoundary'

function mount() {
  let phase = 'ready'; let generation = 1
  const finish = vi.fn().mockResolvedValue(false)
  const recoverFinish = vi.fn().mockResolvedValue(undefined)
  const suspendConnection = vi.fn(); const resumeConnection = vi.fn()
  bridge.listen.mockImplementation(async (_: string, callback: () => Promise<void>) => { bridge.close = callback; return () => {} })
  bridge.invoke.mockImplementation(async (command: string) => command === 'desktop_status' ? { phase, generation, version: '1.0.0-beta.1' } : undefined)
  function Child() {
    useDesktopLifecycle({ finish, recoverFinish, suspendConnection, resumeConnection, ended: false } as unknown as ReturnType<typeof useChampionWorkspace>)
    const [value, setValue] = useState('draft')
    return <input aria-label="local draft" value={value} onChange={(event) => setValue(event.target.value)} />
  }
  render(<DesktopHost><Child /></DesktopHost>)
  return { finish, recoverFinish, suspendConnection, resumeConnection,
    crash: () => { phase = 'failed' }, reconnect: () => { phase = 'ready'; generation++ } }
}

afterEach(() => vi.useRealTimers())
describe('native window lifecycle', () => {
  it('retains a mounted draft on crash and reconnects without closing or starting automation', async () => {
    vi.useFakeTimers()
    const workspace = mount()
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'my changes' } })
    workspace.crash()
    await act(async () => { await vi.advanceTimersByTimeAsync(800) })
    expect(screen.getByText('Bağlantıyı yeniden kuralım.')).toBeVisible()
    expect(workspace.suspendConnection).toHaveBeenCalledOnce()
    workspace.reconnect()
    await act(async () => { await vi.advanceTimersByTimeAsync(800) })
    expect(screen.getByRole('textbox')).toHaveValue('my changes')
    expect(workspace.resumeConnection).toHaveBeenCalledOnce()
    expect(bridge.invoke.mock.calls.every(([command]) => command === 'desktop_status')).toBe(true)
  })

  it('waits for the final save and confirmed Stop; a refused guard keeps the window open', async () => {
    const workspace = mount()
    await screen.findByRole('textbox')
    await act(async () => { await bridge.close?.() })
    expect(bridge.invoke).not.toHaveBeenCalledWith('desktop_close')
    const pending = deferred<boolean>()
    workspace.finish.mockReturnValueOnce(pending.promise)
    let closed: Promise<void> | undefined
    await act(async () => { closed = bridge.close?.() })
    expect(bridge.invoke).not.toHaveBeenCalledWith('desktop_close')
    await act(async () => { pending.resolve(true); await closed })
    expect(bridge.invoke).toHaveBeenCalledWith('desktop_close')
  })

  it('requires explicit form-discard confirmation after a render error and preserves the window on failed recovery', async () => {
    const workspace = mount()
    await screen.findByRole('textbox')
    workspace.recoverFinish.mockRejectedValueOnce(new Error('save/stop failed'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    function Broken(): never { throw new Error('private details') }
    render(<AppErrorBoundary><Broken /></AppErrorBoundary>)
    expect(screen.queryByRole('button', { name: 'Arayüzü yeniden yükle' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Otomasyonu durdur ve kapat' }))
    expect(workspace.recoverFinish).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Evet, güvenli biçimde kapat' }))
    await waitFor(() => expect(screen.getByText(/Kayıt veya otomasyonun durması doğrulanamadı/)).toBeVisible())
    expect(bridge.invoke).not.toHaveBeenCalledWith('desktop_close')
    await recoverDesktopSession()
    expect(bridge.invoke).toHaveBeenCalledWith('desktop_close')
  })
})
