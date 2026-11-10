import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AppErrorBoundary } from './AppErrorBoundary'

describe('unexpected UI errors', () => {
  it('leaves a healthy application visible', () => {
    render(<AppErrorBoundary><p>Healthy editor</p></AppErrorBoundary>)
    expect(screen.getByText('Healthy editor')).toBeVisible()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('shows a recoverable message instead of a blank screen without leaking exception details', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const reload = vi.fn()
    function BrokenEditor(): never { throw new Error('Private diagnostic details') }
    render(<AppErrorBoundary onReload={reload}><BrokenEditor /></AppErrorBoundary>)
    expect(screen.getByRole('alert')).toBeVisible()
    expect(screen.getByText('Arayüz görüntülenemedi')).toBeVisible()
    expect(screen.queryByText('Private diagnostic details')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Arayüzü yeniden yükle' }))
    expect(reload).toHaveBeenCalledOnce()
  })
})
