import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { PilotApi, Settings } from '../../api/contracts'
import { catalog, health, settings } from '../../test/fixtures'

// Model React Fast Refresh discarding memo caches while retaining hook state.
// A workspace must retain its draft/command controllers in this environment.
vi.mock('react', async (original) => ({
  ...await original<typeof import('react')>(),
  useMemo: <T,>(factory: () => T) => factory(),
}))
import { useChampionWorkspace } from './useChampionWorkspace'

it('preserves loaded selections and unsaved changes when memo caches are discarded', async () => {
  const client = { health: vi.fn().mockResolvedValue(health), settings: vi.fn().mockResolvedValue(settings),
    champions: vi.fn().mockResolvedValue(catalog), saveSettings: vi.fn(async (config: Settings) => config),
    start: vi.fn(), update: vi.fn(), stop: vi.fn(), runeCatalog: vi.fn(), recommendedRune: vi.fn(),
    validateRune: vi.fn(), skins: vi.fn() } satisfies PilotApi
  const { result, rerender } = renderHook(() => useChampionWorkspace(client))
  await waitFor(() => expect(result.current.ready).toBe(true))
  expect(result.current.draft).toEqual(settings)
  act(() => result.current.editSettings({ queue_name: 'Ranked Flex' }))
  rerender()
  expect(result.current.draft?.queue_name).toBe('Ranked Flex')
  expect(result.current.dirty).toBe(true)
  act(() => result.current.save())
  await waitFor(() => expect(result.current.dirty).toBe(false))
  expect(client.saveSettings).toHaveBeenCalledWith(expect.objectContaining({ queue_name: 'Ranked Flex' }))
  expect(client.settings).toHaveBeenCalledTimes(1)
  expect(client.start).not.toHaveBeenCalled()
})
