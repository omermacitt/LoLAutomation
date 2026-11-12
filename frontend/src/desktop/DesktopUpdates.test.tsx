import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'
import { deferred } from '../test/fixtures'

const bridge = vi.hoisted(() => ({ invoke: vi.fn() }))
vi.mock('@tauri-apps/api/core', () => ({ invoke: bridge.invoke, isTauri: () => true }))
vi.mock('@tauri-apps/api/event', () => ({ listen: vi.fn().mockResolvedValue(() => {}) }))
import { DesktopUpdates } from './DesktopUpdates'

it('uses the current rune/save/Stop guards after a download, not the render that started it', async () => {
  const downloaded = deferred<void>()
  bridge.invoke.mockImplementation(async (command) => command === 'desktop_update_check'
    ? { enabled: true, channel: 'stable', update: { version: '1.0.1', current_version: '1.0.0', notes: 'Test notes' } }
    : command === 'desktop_update_download' ? downloaded.promise : undefined)
  const originalPrepare = vi.fn().mockResolvedValue(true)
  const latestPrepare = vi.fn().mockResolvedValue(false)
  const release = vi.fn()
  const workspace = { prepareUpdate: originalPrepare, cancelUpdate: release, closing: false, ended: false } as unknown as ReturnType<typeof useChampionWorkspace>
  const { rerender } = render(<><div id="desktop-update-panel" /><DesktopUpdates workspace={workspace} /></>)
  fireEvent.click(screen.getByRole('button', { name: 'Güncellemeleri kontrol et' }))
  fireEvent.click(await screen.findByRole('button', { name: /^Güncelle$/ }))
  rerender(<><div id="desktop-update-panel" /><DesktopUpdates workspace={{ ...workspace, prepareUpdate: latestPrepare }} /></>)
  await act(async () => downloaded.resolve())
  await waitFor(() => expect(latestPrepare).toHaveBeenCalledOnce())
  expect(originalPrepare).not.toHaveBeenCalled()
  expect(bridge.invoke).not.toHaveBeenCalledWith('desktop_update_install')
  expect(release).toHaveBeenCalledOnce()
  expect(await screen.findByRole('alert')).toHaveTextContent('Güncelleme başlamadı')
})
