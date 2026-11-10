import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { deferred, health } from '../test/fixtures'
import { SelectionAlert } from './SelectionAlert'
import { playSelectionSound } from '../features/automation/selectionSound'

vi.mock('../features/automation/selectionSound', () => ({ playSelectionSound: vi.fn().mockResolvedValue(true), stopSelectionSound: vi.fn() }))
const notice = { id: 1, code: 'no_preference' as const, role: 'JUNGLE', champion_id: null }

describe('manual selection feedback', () => {
  it('announces once per incident across polls, including StrictMode, and respects mute', async () => {
    const stop = vi.fn()
    const props = { onStop: stop, stopping: false }
    const view = render(<StrictMode><SelectionAlert {...props} health={{ ...health, running: true, selection: notice }} /></StrictMode>)
    await waitFor(() => expect(playSelectionSound).toHaveBeenCalledTimes(1))
    expect(screen.getByRole('alert')).toHaveTextContent('Orman için şampiyon tercihi yok')
    view.rerender(<StrictMode><SelectionAlert {...props} health={{ ...health, running: true, selection: { ...notice } }} /></StrictMode>)
    expect(playSelectionSound).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Sesi kapat' }))
    view.rerender(<StrictMode><SelectionAlert {...props} health={{ ...health, running: true, selection: { ...notice, id: 2 } }} /></StrictMode>)
    expect(playSelectionSound).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('alert')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Otomasyonu durdur' }))
    expect(stop).toHaveBeenCalledOnce()
    view.rerender(<StrictMode><SelectionAlert {...props} health={{ ...health, running: false, selection: notice }} /></StrictMode>)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('keeps a visible fallback when browser audio is blocked and allows a user retry', async () => {
    vi.mocked(playSelectionSound).mockResolvedValueOnce(false).mockResolvedValueOnce(true)
    render(<SelectionAlert health={{ ...health, running: true, selection: notice }} onStop={vi.fn()} stopping={false} />)
    await screen.findByText('Ses çalınamadı.', { exact: false })
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Uyarıyı dinle' })))
    expect(screen.queryByText('Ses çalınamadı.', { exact: false })).toBeNull()
    expect(screen.getByRole('alert')).toBeVisible()
  })

  it('shows manual hover without sounding an urgent alert and clears after confirmation', () => {
    const props = { onStop: vi.fn(), stopping: false }
    const view = render(<SelectionAlert {...props} health={{ ...health, running: true, selection: { ...notice, code: 'manual_hover', champion_id: 238 } }} />)
    expect(playSelectionSound).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toHaveTextContent('Manuel şampiyon seçimi algılandı')
    view.rerender(<SelectionAlert {...props} health={{ ...health, running: true, selection: null }} />)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('invalidates delayed audio when muted and ignores the old blocked result', async () => {
    const pending = deferred<boolean>()
    let allowed: (() => boolean) | undefined
    vi.mocked(playSelectionSound).mockImplementationOnce((guard) => { allowed = guard; return pending.promise })
    render(<SelectionAlert health={{ ...health, running: true, selection: notice }} onStop={vi.fn()} stopping={false} />)
    await waitFor(() => expect(allowed).toBeDefined())
    fireEvent.click(screen.getByRole('button', { name: 'Sesi kapat' }))
    expect(allowed!()).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Sesi aç' }))
    expect(allowed!()).toBe(false) // Re-enabling sound cannot revive the cancelled attempt.
    await act(async () => pending.resolve(false))
    expect(screen.queryByText('Ses çalınamadı.', { exact: false })).toBeNull()
  })

  it('retains a known manual warning during a connection failure until a confirmed clear', async () => {
    const props = { onStop: vi.fn(), stopping: false }
    const view = render(<SelectionAlert {...props} health={{ ...health, running: true, selection: notice }} />)
    await waitFor(() => expect(playSelectionSound).toHaveBeenCalledTimes(1))
    view.rerender(<SelectionAlert {...props} health={undefined} />)
    expect(screen.getByRole('alert')).toBeVisible()
    expect(screen.getByText('Bağlantı doğrulanamıyor.', { exact: false })).toBeVisible()
    expect(playSelectionSound).toHaveBeenCalledTimes(1)
    view.rerender(<SelectionAlert {...props} health={{ ...health, running: true, selection: null }} />)
    expect(screen.queryByRole('alert')).toBeNull()
  })
})
