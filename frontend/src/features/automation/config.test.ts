import { describe, expect, it } from 'vitest'
import { catalog, settings } from '../../test/fixtures'
import { automationIssues, autofillWarnings, automationPayload, movePick, selectChampion, setSpell } from './config'

describe('selection to automation contract', () => {
  it('preserves unavailable saved choices but omits them from the runtime payload', () => {
    const config = { ...settings, role_champions_ui: { TOP: [999999, 266, 266] }, custom_runes: { '266': { '1': { name: 'keep' } } }, custom_skins: { TOP: { '266': 266001 } } }
    const payload = automationPayload(config, catalog)
    expect(payload.role_champions.TOP).toEqual([266])
    expect(config.role_champions_ui.TOP).toEqual([999999, 266, 266])
    expect(payload.custom_runes).toEqual(config.custom_runes)
    expect(payload.custom_skins).toEqual(config.custom_skins)
    expect(payload.queue_id).toBe(420)
    expect(payload.primary_role).toBe('TOP')
  })

  it('updates spells per role/champion and clears only the conflicting spell', () => {
    const config = structuredClone(settings)
    config.custom_summoner_spells = { TOP: { '266': { spell1Id: 4, spell2Id: 14 } }, MIDDLE: { '103': { spell1Id: 4, spell2Id: 12 } } }
    const edited = setSpell(config, 'TOP', 266, 'spell2Id', 4)
    expect(edited.custom_summoner_spells.TOP['266']).toEqual({ spell1Id: null, spell2Id: 4 })
    expect(edited.custom_summoner_spells.MIDDLE).toEqual(config.custom_summoner_spells.MIDDLE)
    expect(config.custom_summoner_spells.TOP['266'].spell1Id).toBe(4)
  })

  it('inherits a known skin for a newly chosen role without losing existing settings', () => {
    const config = { ...structuredClone(settings), custom_skins: { MIDDLE: { '103': 103001 } } }
    const edited = selectChampion(config, 'TOP', { kind: 'pick', index: 1 }, 103)
    expect(edited.custom_skins.TOP).toEqual({ '103': 103001 })
    expect(edited.custom_skins.MIDDLE).toEqual(config.custom_skins.MIDDLE)
    expect(config.role_champions_ui.TOP).toEqual([266, 86, 122])
  })

  it('requires an owned/free choice and a known ban for the preferred roles before Start', () => {
    const missing = automationIssues({ ...settings, role_champions_ui: { TOP: [84] } }, catalog)
    expect(missing).toContain('Üst koridor: en az bir seçilebilir şampiyon belirle.')
    expect(missing).toContain('Orta koridor: yasaklanacak bir şampiyon belirle.')
    expect(missing).not.toContain('Orman: yasaklanacak bir şampiyon belirle.')
  })

  it('allows Mid/ADC-only preparation and warns about autofill coverage instead of blocking Start', () => {
    const config = { ...settings, primary_role_name: 'Mid', secondary_role_name: 'ADC',
      role_champions_ui: { MIDDLE: [103], BOTTOM: [22] }, role_bans_ui: { MIDDLE: 84, BOTTOM: 84 } }
    expect(automationIssues(config, catalog)).toEqual([])
    expect(autofillWarnings(config, catalog)).toEqual(['Üst koridor', 'Orman', 'Destek'])
  })

  it('reorders without dropping missing IDs or unique extra legacy rows', () => {
    const config = { ...settings, role_champions_ui: { TOP: [999999, 266, 86, 103] } }
    expect(movePick(config, 'TOP', 0, 1).role_champions_ui.TOP).toEqual([266, 999999, 86, 103])
    expect(config.role_champions_ui.TOP).toEqual([999999, 266, 86, 103])
  })

  it('rejects a duplicate pick without changing other settings and allows cross-role or ban reuse', () => {
    const original = structuredClone(settings)
    expect(selectChampion(original, 'TOP', { kind: 'pick', index: 1 }, 266)).toBe(original)
    expect(selectChampion(original, 'TOP', { kind: 'pick', index: 0 }, 266).role_champions_ui.TOP).toEqual([266, 86, 122])
    expect(selectChampion(original, 'MIDDLE', { kind: 'pick', index: 1 }, 266).role_champions_ui.MIDDLE).toEqual([103, 266, null])
    expect(selectChampion(original, 'TOP', { kind: 'ban' }, 266).role_bans_ui.TOP).toBe(266)
  })
})
