import { describe, expect, it } from 'vitest'
import { blockSlots, calculateStats } from './model'
import type { BuilderItem, ChampionItemStats, ItemSet } from '../../api/itemSets'

const zero = { ad: 0, ap: 0, hp: 0, armor: 0, mr: 0, attack_speed: 0, haste: 0 }
const champion: ChampionItemStats = { champion_id: 107, version: '16.22.1', base: { ...zero, ad: 68, hp: 590, armor: 34, mr: 32, attack_speed: .667 }, growth: { ...zero, ad: 3, hp: 104, armor: 4.2, mr: 2.05, attack_speed: 3 }, attack_speed_ratio: .667 }
const item: BuilderItem = { id: 3078, name: 'Üçlü Kuvvet', price: 3333, stats: { ...zero, ad: 36, hp: 333, haste: 15, attack_speed: .3 }, tags: [], description: '' }
describe('level and direct item calculation', () => {
  it('uses the nonlinear growth curve at level 2 and total 17 growth at level 18', () => {
    expect(calculateStats(champion, 1, []).total.ad).toBe(68)
    expect(calculateStats(champion, 2, []).total.ad).toBeCloseTo(70.16)
    const result = calculateStats(champion, 18, [item])
    expect(result.total.ad).toBe(155)
    expect(result.total.hp).toBe(2691)
    expect(result.total.ap).toBe(0)
    expect(result.total.haste).toBe(15)
    expect(result.total.attack_speed).toBeCloseTo(.667 + .667 * (.51 + .3))
    expect(result.bonus.ad).toBe(36)
  })
  it('rejects invalid level and more than six equipped items', () => {
    for (const level of [0, 19, 1.5]) expect(() => calculateStats(champion, level, [])).toThrow()
    expect(() => calculateStats(champion, 1, Array(7).fill(item))).toThrow()
  })
  it('preserves empty inventory positions and calculates only the active block', () => {
    const set: ItemSet = { uid: 'x', title: 'x', champion_id: 107, map_id: 11, blocks: [{ name: 'One', items: [{ id: 3078, count: 1 }], slots: [null, null, null, null, null, 3078] }, { name: 'Two', items: [] }] }
    expect(blockSlots(set, 0)).toEqual([null, null, null, null, null, 3078])
    expect(blockSlots(set, 1)).toEqual([null, null, null, null, null, null])
  })
})
