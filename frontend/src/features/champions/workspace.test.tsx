import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ChampionCatalog, PilotApi, Settings, RunePage } from '../../api/contracts'
import { catalog, deferred, health, settings } from '../../test/fixtures'
import { runePage } from '../../test/runeFixtures'
import { useChampionWorkspace } from './useChampionWorkspace'
import { roles } from './selection'

function makeApi(): PilotApi {
  return { health: vi.fn().mockResolvedValue(health), settings: vi.fn().mockResolvedValue(settings), champions: vi.fn().mockResolvedValue(catalog),
    saveSettings: vi.fn(async (config: Settings) => config), start: vi.fn(), update: vi.fn(), stop: vi.fn().mockResolvedValue(undefined),
    runeCatalog: vi.fn(), recommendedRune: vi.fn(), validateRune: vi.fn(async (page) => page), skins: vi.fn() }
}

describe('champion workspace ordering and data safety', () => {
  it('recovers an unmounted dirty rune workspace through save and Stop errors without stale render gates', async () => {
    const api = makeApi()
    const pending = deferred<Settings>()
    vi.mocked(api.saveSettings).mockImplementationOnce(() => pending.promise)
    const { result, unmount } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.editSettings({ queue_name: 'Ranked Flex' }))
    act(() => result.current.setRuneEditorDirty(true))
    const recover = result.current.recoverFinish
    unmount()
    const recovering = recover()
    expect(api.stop).not.toHaveBeenCalled()
    const failed = expect(recovering).rejects.toThrow('disk full')
    pending.reject(new Error('disk full'))
    await failed
    expect(api.stop).not.toHaveBeenCalled()
    vi.mocked(api.stop).mockRejectedValueOnce(new Error('stop failed'))
    await expect(recover()).rejects.toThrow('stop failed')
    expect(api.saveSettings).toHaveBeenLastCalledWith(expect.objectContaining({ queue_name: 'Ranked Flex' }))
    await recover()
    expect(api.stop).toHaveBeenCalledTimes(2)
    expect(api.start).not.toHaveBeenCalled()
  })
  it('waits for rune validation before merging and acknowledging a preset', async () => {
    const validation = deferred<RunePage>()
    const api = makeApi()
    vi.mocked(api.validateRune).mockImplementationOnce(() => validation.promise)
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    let save!: Promise<void>
    act(() => { save = result.current.saveRunePreset(266, 2, runePage, 'TOP') })
    expect(result.current.runeBusy).toBe(true)
    act(() => result.current.choose(103))
    await act(async () => result.current.finish())
    expect(api.saveSettings).not.toHaveBeenCalled()
    expect(api.stop).not.toHaveBeenCalled()
    await act(async () => { validation.resolve(runePage); await save })
    expect(result.current.saveState.saved?.role_rune_selection.TOP['266']).toBe(2)
    expect(result.current.saveState.saved?.role_champions_ui).toEqual(settings.role_champions_ui)
    expect(result.current.runeBusy).toBe(false)
    expect(api.start).not.toHaveBeenCalled()
  })

  it('does not change settings if the current catalog rejects the rune page', async () => {
    const api = makeApi()
    vi.mocked(api.validateRune).mockRejectedValueOnce(new Error('invalid rune'))
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    await act(async () => { await expect(result.current.saveRunePreset(266, 1, runePage, 'TOP')).rejects.toThrow('invalid rune') })
    expect(result.current.saveState.saved).toEqual(settings)
    expect(result.current.dirty).toBe(false)
    expect(api.saveSettings).not.toHaveBeenCalled()
  })

  it('blocks Start and controlled exit while an editor has unsaved rune choices', async () => {
    const api = makeApi()
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.setRuneEditorDirty(true))
    await act(async () => result.current.start())
    await act(async () => result.current.finish())
    expect(result.current.ended).toBe(false)
    expect(api.start).not.toHaveBeenCalled()
    expect(api.stop).not.toHaveBeenCalled()
    expect(api.saveSettings).not.toHaveBeenCalled()
  })

  it('guards duplicate choices even if a stale click bypasses the disabled card', async () => {
    const api = makeApi()
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.setTarget({ kind: 'pick', index: 1 }))
    act(() => result.current.choose(266))
    expect(result.current.draft?.role_champions_ui.TOP).toEqual([266, 86, 122])
    expect(result.current.dirty).toBe(false)
    expect(api.saveSettings).not.toHaveBeenCalled()
    act(() => result.current.choose(103))
    expect(result.current.draft?.role_champions_ui.TOP).toEqual([266, 103, 122])
    expect(result.current.draft?.role_champions_ui.MIDDLE).toEqual([103, null, null])
  })

  it.each(['settings-first', 'catalog-first'])('waits for both responses (%s)', async (order) => {
    const config = deferred<Settings>()
    const champions = deferred<ChampionCatalog>()
    const api = { ...makeApi(), settings: vi.fn(() => config.promise), champions: vi.fn(() => champions.promise) }
    const { result } = renderHook(() => useChampionWorkspace(api))
    await act(async () => { if (order === 'settings-first') config.resolve(settings); else champions.resolve(catalog) })
    expect(result.current.ready).toBe(false)
    act(() => result.current.choose(103))
    expect(result.current.dirty).toBe(false)
    await act(async () => { if (order === 'settings-first') champions.resolve(catalog); else config.resolve(settings) })
    expect(result.current.ready).toBe(true)
    expect(result.current.draft?.role_champions_ui.TOP).toEqual([266, 86, 122])
  })

  it('retains edits and unknown saved IDs across catalog errors and retry', async () => {
    const api = makeApi()
    vi.mocked(api.settings).mockResolvedValue({ ...settings, role_champions_ui: { TOP: [999999, 266, 122] } })
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.draft?.role_champions_ui.TOP).toEqual([999999, 266, 122])
    act(() => result.current.setTarget({ kind: 'pick', index: 1 }))
    act(() => result.current.choose(103))
    vi.mocked(api.champions).mockRejectedValueOnce(new Error('offline'))
    act(() => result.current.retry())
    await waitFor(() => expect(result.current.catalog.error).toBe('offline'))
    expect(result.current.ready).toBe(false)
    expect(result.current.draft?.role_champions_ui.TOP).toEqual([999999, 103, 122])
    act(() => result.current.retry())
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.draft?.role_champions_ui.TOP).toEqual([999999, 103, 122])
    expect(api.settings).toHaveBeenCalledTimes(1)
  })

  it('never creates defaults when settings fail and can recover on retry', async () => {
    const api = makeApi()
    vi.mocked(api.settings).mockRejectedValueOnce(new Error('settings failed'))
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.settings.error).toBe('settings failed'))
    expect(result.current.draft).toBeUndefined()
    expect(result.current.ready).toBe(false)
    act(() => result.current.choose(103))
    expect(result.current.dirty).toBe(false)
    act(() => result.current.retry())
    await waitFor(() => expect(result.current.ready).toBe(true))
    expect(result.current.draft?.role_champions_ui.TOP).toEqual(settings.role_champions_ui.TOP)
  })

  it('ignores late responses from an abandoned retry', async () => {
    const stale = deferred<ChampionCatalog>()
    const api = makeApi()
    vi.mocked(api.champions).mockImplementationOnce(() => stale.promise)
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.settings.data).toBeDefined())
    act(() => result.current.retry())
    await waitFor(() => expect(result.current.ready).toBe(true))
    await act(async () => stale.resolve({ all_champions: [{ id: 1, name: 'Stale' }], pickable_champions: [] }))
    expect(result.current.catalog.data).toEqual(catalog)
  })

  it('allows all catalog champions for bans but only pickable ones for picks; reset restores the snapshot', async () => {
    const { result } = renderHook(() => useChampionWorkspace(makeStableApi))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.choose(84))
    expect(result.current.dirty).toBe(false)
    act(() => result.current.setTarget({ kind: 'ban' }))
    act(() => result.current.choose(84))
    expect(result.current.draft?.role_bans_ui.TOP).toBe(84)
    act(() => result.current.choose(null))
    expect(result.current.draft?.role_bans_ui.TOP).toBeNull()
    act(() => result.current.reset())
    await waitFor(() => expect(result.current.dirty).toBe(false))
    expect(result.current.draft?.role_bans_ui.TOP).toBe(84)
    expect(settings.role_bans_ui.TOP).toBe(84)
  })

  it('keeps the session open and never stops the engine when the final save fails', async () => {
    const api = makeApi()
    vi.mocked(api.saveSettings).mockRejectedValueOnce(new Error('save failed'))
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.choose(103))
    await act(async () => result.current.finish())
    expect(result.current.ended).toBe(false)
    expect(result.current.dirty).toBe(true)
    expect(result.current.draft?.role_champions_ui.TOP[0]).toBe(103)
    expect(api.stop).not.toHaveBeenCalled()
    expect(result.current.actionError).toBe('save failed')
    await act(async () => result.current.finish())
    expect(result.current.ended).toBe(true)
    expect(api.stop).toHaveBeenCalledTimes(1)
    expect(result.current.dirty).toBe(false)
  })

  it('cancels a prepared Start if Stop arrives while its final save is pending', async () => {
    const api = makeApi()
    const complete = structuredClone(settings)
    for (const role of roles) {
      complete.role_champions_ui[role.key] = [266, null, null]
      complete.role_bans_ui[role.key] = 84
    }
    vi.mocked(api.settings).mockResolvedValue(complete)
    const pending = deferred<Settings>()
    vi.mocked(api.saveSettings).mockImplementationOnce(() => pending.promise)
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready && result.current.health.data).toBeTruthy())
    act(() => result.current.editSettings({ queue_name: 'Ranked Flex' }))
    let start!: Promise<void>
    act(() => { start = result.current.start() })
    expect(api.start).not.toHaveBeenCalled()
    await act(async () => result.current.stop())
    await act(async () => { pending.resolve({ ...complete, queue_name: 'Ranked Flex' }); await start })
    expect(api.start).not.toHaveBeenCalled()
    expect(api.stop).toHaveBeenCalledTimes(1)
  })

  it('applies the first acknowledged edit after a delayed health poll confirms a running engine', async () => {
    const api = makeApi()
    const pendingHealth = deferred<typeof health>()
    vi.mocked(api.health).mockImplementationOnce(() => pendingHealth.promise)
    vi.mocked(api.update).mockImplementation(async (config) => ({ status: 'updated', config }))
    const { result } = renderHook(() => useChampionWorkspace(api))
    await waitFor(() => expect(result.current.ready).toBe(true))
    act(() => result.current.choose(103))
    act(() => result.current.save())
    await waitFor(() => expect(result.current.dirty).toBe(false))
    expect(api.update).not.toHaveBeenCalled()
    await act(async () => pendingHealth.resolve({ ...health, running: true }))
    await waitFor(() => expect(api.update).toHaveBeenCalledTimes(1))
    expect(api.start).not.toHaveBeenCalled()
  })
})

const makeStableApi = makeApi()
