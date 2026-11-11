import { describe, expect, it } from 'vitest'
import { settings } from '../../test/fixtures'
import { runeCatalog, runePage } from '../../test/runeFixtures'
import { affectedRoles, assignPreset, changePrimary, chooseSecondary, pageIssues, preset, restorePreset, runeChoice, selectedPreset, withPreset, withoutPreset } from './model'

describe('rune page rules and shared champion presets', () => {
  it('distinguishes explicit recommendation, missing assignment and missing preset', () => {
    const config = { ...structuredClone(settings), custom_runes: { '106': { '1': runePage, '2': runePage } }, rune_selection: { '106': 1 },
      role_rune_selection: { TOP: { '106': 0 }, MIDDLE: { '106': 2 }, JUNGLE: { '106': 3 } } }
    expect(selectedPreset(config, 106, 'TOP')).toBe(0)
    expect(selectedPreset(config, 106, 'MIDDLE')).toBe(2)
    expect(selectedPreset(config, 106, 'BOTTOM')).toBe(1)
    expect(runeChoice(config, 106, 'JUNGLE')).toEqual({ slot: 0, explicit: true, unavailable: true })
    expect(selectedPreset(assignPreset(config, 106, null, 'TOP'), 106, 'TOP')).toBe(1)
    expect(affectedRoles(config, 106, 1)).toEqual(['Alt koridor', 'Destek'])
  })
  it('saves shared content but assigns only its target role and deletion prevents legacy revival', () => {
    const config = { ...structuredClone(settings), custom_runes: { '106': { '1': runePage, '2': runePage } }, rune_selection: { '106': 1 },
      role_rune_selection: { TOP: { '106': 1 }, MIDDLE: { '106': 2 } } }
    const next = withPreset(config, 106, 2, { ...runePage, name: 'Shared' }, 'TOP')
    expect(next.role_rune_selection).toEqual({ TOP: { '106': 2 }, MIDDLE: { '106': 2 } })
    expect(next.rune_selection).toEqual(config.rune_selection)
    const deleted = withoutPreset(next, 106, 2)
    expect(deleted.role_rune_selection).toEqual({ TOP: { '106': 0 }, MIDDLE: { '106': 0 } })
    expect(selectedPreset(deleted, 106, 'TOP')).toBe(0)
    expect(restorePreset(deleted, next, 106, 2)).toEqual(next)
  })
  it('undo preserves missing versus zero and another role changed after a failed save', () => {
    for (const original of [undefined, 0] as const) {
      const saved = structuredClone(settings)
      if (original !== undefined) saved.role_rune_selection = { TOP: { '106': original } }
      const failed = withPreset(saved, 106, 1, runePage, 'TOP')
      const later = assignPreset(failed, 106, 2, 'MIDDLE')
      const restored = restorePreset(later, saved, 106, 1, 'TOP')
      expect(restored.role_rune_selection.TOP?.['106']).toBe(original)
      expect(restored.role_rune_selection.MIDDLE['106']).toBe(2)
      expect(restored.custom_runes['106']).toBeUndefined()
    }
  })
  it('restores only a failed preset context, leaving another pending preset and selection intact', () => {
    const saved = withPreset(structuredClone(settings), 266, 1, runePage)
    const pending = withPreset(saved, 266, 2, { ...runePage, name: 'Pending' })
    expect(restorePreset(pending, saved, 266, 1)).toEqual(pending)
    expect(restorePreset(pending, saved, 266, 2)).toEqual(saved)
    const deleted = withoutPreset(saved, 266, 1)
    expect(restorePreset(deleted, saved, 266, 1)).toEqual(saved)
  })

  it('allows repeated shards and validates their individual rows', () => {
    expect(pageIssues(runePage, runeCatalog)).toEqual([])
    expect(pageIssues({ ...runePage, selectedPerkIds: [...runePage.selectedPerkIds.slice(0, 8), 5008] }, runeCatalog)).toHaveLength(1)
  })
  it('replaces a secondary choice in its row and drops the oldest when selecting a third row', () => {
    const second = runeCatalog.styles[1]
    const replaced = chooseSecondary(runePage, second, 8112)
    expect(replaced.selectedPerkIds.slice(4, 6)).toEqual([8112, 8121])
    const third = chooseSecondary(replaced, second, 8131)
    expect(third.selectedPerkIds.slice(4, 6)).toEqual([8121, 8131])
    expect(pageIssues(third, runeCatalog)).toEqual([])
    expect(pageIssues({ ...third, selectedPerkIds: [8001, 8011, 8021, 8031, 8111, 8112, 5008, 5008, 5001] }, runeCatalog)).toHaveLength(1)
  })
  it('changing primary fixes a conflicting secondary, preserves name and valid shards', () => {
    const next = changePrimary(runePage, 8100, runeCatalog)
    expect(next.subStyleId).toBe(8000)
    expect(next.name).toBe(runePage.name)
    expect(next.selectedPerkIds.slice(6)).toEqual(runePage.selectedPerkIds.slice(6))
    expect(pageIssues(next, runeCatalog)).toEqual([])
    expect(changePrimary(next, 8100, runeCatalog)).toBe(next)
  })
  it('updates only the selected shared preset, preserves siblings and clears selection when deleted', () => {
    const original = { ...structuredClone(settings), custom_skins: { TOP: { '266': 266001 } } }
    const first = withPreset(original, 103, 2, runePage)
    const second = withPreset(first, 266, 1, runePage)
    const third = withPreset(second, 266, 3, { ...runePage, name: 'Other' })
    expect(selectedPreset(third, 266)).toBe(3)
    const removed = withoutPreset(third, 266, 3)
    expect(selectedPreset(removed, 266)).toBe(0)
    expect(preset(removed, 266, 1)).toEqual(runePage)
    expect(preset(removed, 103, 2)).toEqual(runePage)
    expect(removed.custom_skins).toEqual(original.custom_skins)
    expect(removed.role_champions_ui).toEqual(original.role_champions_ui)
    expect(original.custom_runes).toEqual({})
  })
})
