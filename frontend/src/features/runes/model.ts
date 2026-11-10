import { runePageSchema } from '../../api/contracts'
import type { RuneEditorCatalog, RunePage, RuneStyle, Settings } from '../../api/contracts'

export type PresetSlot = 1 | 2 | 3
export const presetSlots: PresetSlot[] = [1, 2, 3]
export function preset(config: Settings | undefined, championId: number, slot: PresetSlot): RunePage | undefined {
  const raw = (config?.custom_runes[String(championId)] as Record<string, unknown> | undefined)?.[String(slot)]
  const parsed = runePageSchema.safeParse(raw)
  return parsed.success ? parsed.data : undefined
}
export function hasPreset(config: Settings | undefined, championId: number, slot: PresetSlot): boolean {
  const pages = config?.custom_runes[String(championId)]
  return Boolean(pages && typeof pages === 'object' && String(slot) in pages)
}
export function selectedPreset(config: Settings | undefined, championId: number): number {
  const selected = config?.rune_selection[String(championId)]
  return presetSlots.includes(selected as PresetSlot) && hasPreset(config, championId, selected as PresetSlot) ? selected! : 0
}
export function defaultPage(catalog: RuneEditorCatalog, name: string): RunePage {
  const primary = catalog.styles[0]
  const secondary = catalog.styles.find((style) => primary.allowedSubStyles.includes(style.id))!
  return { name: `Custom ${name}`.slice(0, 16), primaryStyleId: primary.id, subStyleId: secondary.id,
    selectedPerkIds: [...primary.rows.map((row) => row[0].id), secondary.rows[1][0].id, secondary.rows[2][0].id, ...primary.shardRows.map((row) => row[0].id)] }
}
export function pageIssues(page: RunePage, catalog: RuneEditorCatalog): string[] {
  const primary = catalog.styles.find((style) => style.id === page.primaryStyleId)
  const secondary = catalog.styles.find((style) => style.id === page.subStyleId)
  const issues: string[] = []
  if (!page.name.trim() || page.name.length > 16) issues.push('Preset adı 1–16 karakter olmalı.')
  if (!primary || !secondary || !primary.allowedSubStyles.includes(secondary.id)) return [...issues, 'Farklı ve uyumlu iki rün yolu seç.']
  if (page.selectedPerkIds.length !== 9) return [...issues, 'Dokuz rün seçimi tamamlanmalı.']
  if (primary.rows.some((row, index) => !row.some((perk) => perk.id === page.selectedPerkIds[index]))) issues.push('Ana yolun her satırından bir rün seç.')
  const rows = page.selectedPerkIds.slice(4, 6).map((id) => secondary.rows.findIndex((row, index) => index > 0 && row.some((perk) => perk.id === id)))
  if (rows.some((index) => index < 1) || rows[0] === rows[1]) issues.push('İkincil rünler iki farklı satırdan seçilmeli.')
  if (primary.shardRows.some((row, index) => !row.some((perk) => perk.id === page.selectedPerkIds[index + 6]))) issues.push('Her nitelik satırından bir seçim yap.')
  return issues
}
export function changePrimary(page: RunePage, id: number, catalog: RuneEditorCatalog): RunePage {
  if (id === page.primaryStyleId) return page
  const primary = catalog.styles.find((style) => style.id === id)!
  const secondary = catalog.styles.find((style) => primary.allowedSubStyles.includes(style.id) && style.id === page.subStyleId)
    ?? catalog.styles.find((style) => primary.allowedSubStyles.includes(style.id))!
  const secondaryIds = secondary.id === page.subStyleId ? page.selectedPerkIds.slice(4, 6) : [secondary.rows[1][0].id, secondary.rows[2][0].id]
  return { ...page, primaryStyleId: id, subStyleId: secondary.id, selectedPerkIds: [...primary.rows.map((row) => row[0].id), ...secondaryIds,
    ...primary.shardRows.map((row, index) => row.some((perk) => perk.id === page.selectedPerkIds[index + 6]) ? page.selectedPerkIds[index + 6] : row[0].id)] }
}
export function changeSecondary(page: RunePage, style: RuneStyle): RunePage {
  if (style.id === page.subStyleId) return page
  return { ...page, subStyleId: style.id, selectedPerkIds: [...page.selectedPerkIds.slice(0, 4), style.rows[1][0].id, style.rows[2][0].id, ...page.selectedPerkIds.slice(6)] }
}
export function chooseSecondary(page: RunePage, style: RuneStyle, id: number): RunePage {
  const row = style.rows.findIndex((options, index) => index > 0 && options.some((perk) => perk.id === id))
  if (row < 1) return page
  const selected = page.selectedPerkIds.slice(4, 6)
  const sameRow = selected.findIndex((selectedId) => style.rows[row].some((perk) => perk.id === selectedId))
  if (sameRow >= 0) selected[sameRow] = id
  else { selected.shift(); selected.push(id) }
  return { ...page, selectedPerkIds: [...page.selectedPerkIds.slice(0, 4), ...selected, ...page.selectedPerkIds.slice(6)] }
}
export function withPreset(config: Settings, championId: number, slot: PresetSlot, page: RunePage): Settings {
  const id = String(championId)
  return { ...config, custom_runes: { ...config.custom_runes, [id]: { ...(config.custom_runes[id] as object ?? {}), [String(slot)]: structuredClone(page) } }, rune_selection: { ...config.rune_selection, [id]: slot } }
}
export function withoutPreset(config: Settings, championId: number, slot: PresetSlot): Settings {
  const next = structuredClone(config)
  const id = String(championId)
  const pages = next.custom_runes[id] as Record<string, unknown> | undefined
  if (pages) { delete pages[String(slot)]; if (!Object.keys(pages).length) delete next.custom_runes[id] }
  if (next.rune_selection[id] === slot) delete next.rune_selection[id]
  return next
}

export function restorePreset(config: Settings, saved: Settings, championId: number, slot: PresetSlot): Settings {
  const next = structuredClone(config)
  const id = String(championId)
  const baseline = (saved.custom_runes[id] as Record<string, unknown> | undefined)?.[String(slot)]
  const pages = { ...(next.custom_runes[id] as Record<string, unknown> | undefined) }
  const changed = JSON.stringify(pages[String(slot)]) !== JSON.stringify(baseline)
  if (baseline === undefined) delete pages[String(slot)]
  else pages[String(slot)] = structuredClone(baseline)
  if (Object.keys(pages).length) next.custom_runes[id] = pages
  else delete next.custom_runes[id]
  if (config.rune_selection[id] === slot || (changed && saved.rune_selection[id] === slot)) {
    if (saved.rune_selection[id] === undefined) delete next.rune_selection[id]
    else next.rune_selection[id] = saved.rune_selection[id]
  }
  return next
}
