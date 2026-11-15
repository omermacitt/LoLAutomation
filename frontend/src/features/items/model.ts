import type { BuilderItem, ChampionItemStats, ItemSet, ItemStats } from '../../api/itemSets'

export const calculationNote = 'Hesaplama yalnızca şampiyon seviyesi ve eşyaların doğrudan özelliklerini içerir. Pasifler, biriken yükler, rünler ve koşullu güçlendirmeler hesaba dahil değildir.'
export const statLabels: Record<keyof ItemStats, string> = { ad: 'Saldırı gücü (AD)', ap: 'Yetenek gücü (AP)', hp: 'Can', armor: 'Zırh', mr: 'Büyü direnci', attack_speed: 'Saldırı hızı', haste: 'Yetenek hızı' }
export const blankStats = (): ItemStats => ({ ad: 0, ap: 0, hp: 0, armor: 0, mr: 0, attack_speed: 0, haste: 0 })
export function calculateStats(champion: ChampionItemStats, level: number, items: BuilderItem[]) {
  if (!Number.isInteger(level) || level < 1 || level > 18 || items.length > 6) throw new Error('Geçersiz seviye veya eşya sayısı')
  const growth = (level - 1) * (0.7025 + 0.0175 * (level - 1))
  const base = blankStats(); const bonus = blankStats()
  for (const key of Object.keys(base) as (keyof ItemStats)[]) {
    base[key] = champion.base[key] + champion.growth[key] * growth
    bonus[key] = items.reduce((sum, item) => sum + item.stats[key], 0)
  }
  base.attack_speed = champion.base.attack_speed + champion.attack_speed_ratio * champion.growth.attack_speed * growth / 100
  bonus.attack_speed *= champion.attack_speed_ratio
  const total = blankStats()
  for (const key of Object.keys(total) as (keyof ItemStats)[]) total[key] = base[key] + bonus[key]
  return { base, bonus, total }
}
export function newItemSet(championId: number | null): ItemSet {
  return { uid: `runepilot-${crypto.randomUUID()}`, title: 'Yeni eşya seti', champion_id: championId, map_id: 11,
    blocks: [{ name: 'Başlangıç', items: [] }, { name: 'Ana eşyalar', items: [] }, { name: 'Durumsal', items: [] }] }
}
export const blockSlots = (set: ItemSet, block: number) => {
  if (set.blocks[block]?.slots) return [...set.blocks[block].slots!]
  const ids = set.blocks[block]?.items.flatMap((item) => Array<number>(item.count).fill(item.id)) ?? []
  return Array.from({ length: 6 }, (_, i) => ids[i] ?? null)
}
