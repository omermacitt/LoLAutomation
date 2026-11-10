import { describe, expect, it } from 'vitest'
import { skinOptionsSchema } from '../../api/contracts'
import { settings } from '../../test/fixtures'
import { selectedSkin, withSkin } from './model'

const options = { champion_id: 266, skins: [{ id: 266000, name: 'Aatrox' }, { id: 266001, name: 'Justicar' }] }
describe('owned skin selection', () => {
  it('limits a change to the target role and champion while preserving all other settings', () => {
    const original = { ...structuredClone(settings), custom_skins: { TOP: { '103': 103001 }, MIDDLE: { '266': 266002 } },
      custom_runes: { '266': { '1': { name: 'Keep me' } } } }
    const next = withSkin(original, 'TOP', 266, 266001, options)
    expect(selectedSkin(next, 'TOP', 266)).toBe(266001)
    expect(next.custom_skins).toEqual({ TOP: { '103': 103001, '266': 266001 }, MIDDLE: { '266': 266002 } })
    expect(next.custom_runes).toEqual(original.custom_runes)
    expect(next.role_champions_ui).toEqual(original.role_champions_ui)
    expect(selectedSkin(original, 'TOP', 266)).toBe(266000)
    const reset = withSkin(next, 'TOP', 266, 266000, options)
    expect(reset).toEqual(original)
  })
  it('rejects unowned, wrong-champion and stale mismatched results without changing the draft', () => {
    expect(withSkin(settings, 'TOP', 266, 266002, options)).toBe(settings)
    expect(withSkin(settings, 'TOP', 266, 103001, options)).toBe(settings)
    expect(withSkin(settings, 'TOP', 103, 266001, options)).toBe(settings)
  })
  it('keeps a saved unavailable selection rather than silently choosing default', () => {
    const config = { ...settings, custom_skins: { TOP: { '266': 266999 } } }
    expect(selectedSkin(config, 'TOP', 266)).toBe(266999)
    expect(selectedSkin({ ...settings, custom_skins: { TOP: { '266': 'unreadable' } } }, 'TOP', 266)).toBeUndefined()
  })
  it('rejects malformed and mixed-champion skin catalogs at the HTTP boundary', () => {
    expect(skinOptionsSchema.safeParse(options).success).toBe(true)
    expect(skinOptionsSchema.safeParse({ ...options, skins: [{ id: 103000, name: 'Ahri' }] }).success).toBe(false)
    expect(skinOptionsSchema.safeParse({ ...options, skins: [options.skins[1]] }).success).toBe(false)
    expect(skinOptionsSchema.safeParse({ ...options, skins: [...options.skins, options.skins[0]] }).success).toBe(false)
  })
})
