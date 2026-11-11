import { runePageSchema } from '../../api/contracts'
import type { RuneEditorCatalog, RunePage, RuneStyle, Settings } from '../../api/contracts'
import { roles } from '../champions/selection'
import type { RoleKey } from '../champions/selection'

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
export function runeChoice(config: Settings | undefined, championId: number, role: RoleKey, catalog?: RuneEditorCatalog) {
  const entries = config?.role_rune_selection?.[role]
  const explicit = Boolean(entries && Object.hasOwn(entries, String(championId)))
  const selected = explicit ? entries![String(championId)] : config?.rune_selection[String(championId)] ?? 0
  const page = presetSlots.includes(selected as PresetSlot) ? preset(config, championId, selected as PresetSlot) : undefined
  const usable = selected === 0 || Boolean(page && (!catalog || pageIssues(page, catalog).length === 0))
  return { slot: usable ? selected : 0, explicit, unavailable: !usable }
}
export function selectedPreset(config: Settings | undefined, championId: number, role: RoleKey = 'TOP'): number {
  return runeChoice(config, championId, role).slot
}
// Keep an unreadable saved page open for repair, while effective selection uses its fallback.
export function editorPreset(config: Settings | undefined, championId: number, role: RoleKey): 0 | PresetSlot {
  const entries = config?.role_rune_selection?.[role]
  const selected = entries && Object.hasOwn(entries, String(championId)) ? entries[String(championId)] : config?.rune_selection[String(championId)]
  return presetSlots.includes(selected as PresetSlot) && hasPreset(config, championId, selected as PresetSlot) ? selected as PresetSlot : 0
}
export function assignPreset(config: Settings, championId: number, slot: 0 | PresetSlot | null, role: RoleKey): Settings {
  const next = structuredClone(config)
  const entries = { ...next.role_rune_selection?.[role] }
  if (slot === null) delete entries[String(championId)]
  else entries[String(championId)] = slot
  next.role_rune_selection = { ...next.role_rune_selection, [role]: entries }
  if (!Object.keys(entries).length) delete next.role_rune_selection[role]
  return next
}
export function affectedRoles(config: Settings | undefined, championId: number, slot: PresetSlot) {
  return roles.filter((role) => {
    const entries = config?.role_rune_selection?.[role.key]
    const assigned = entries && Object.hasOwn(entries, String(championId)) ? entries[String(championId)] : config?.rune_selection[String(championId)]
    return assigned === slot
  }).map((role) => role.name)
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
export function withPreset(config: Settings, championId: number, slot: PresetSlot, page: RunePage, role: RoleKey = 'TOP'): Settings {
  const id = String(championId)
  return assignPreset({ ...config, custom_runes: { ...config.custom_runes, [id]: { ...(config.custom_runes[id] as object ?? {}), [String(slot)]: structuredClone(page) } } }, championId, slot, role)
}
export function withoutPreset(config: Settings, championId: number, slot: PresetSlot): Settings {
  const next = structuredClone(config)
  const id = String(championId)
  const pages = next.custom_runes[id] as Record<string, unknown> | undefined
  if (pages) { delete pages[String(slot)]; if (!Object.keys(pages).length) delete next.custom_runes[id] }
  if (next.rune_selection[id] === slot) delete next.rune_selection[id]
  for (const entries of Object.values(next.role_rune_selection ?? {})) if (entries[id] === slot) entries[id] = 0
  return next
}

export function restorePreset(config: Settings, saved: Settings, championId: number, slot: PresetSlot, role: RoleKey = 'TOP', preserveAssignments: ReadonlySet<RoleKey> = new Set()): Settings {
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
  for (const item of roles) {
    if (preserveAssignments.has(item.key)) continue
    const current = config.role_rune_selection?.[item.key]?.[id]
    const baselineChoice = saved.role_rune_selection?.[item.key]?.[id]
    const ownSave = item.key === role && current === slot
    const deletedReference = changed && !hasPreset(config, championId, slot) && baseline !== undefined && current === 0 && baselineChoice === slot
    if (ownSave || deletedReference) {
      const entries = { ...next.role_rune_selection?.[item.key] }
      if (baselineChoice === undefined) delete entries[id]
      else entries[id] = baselineChoice
      next.role_rune_selection = { ...next.role_rune_selection, [item.key]: entries }
      if (!Object.keys(entries).length) delete next.role_rune_selection[item.key]
    }
  }
  return next
}
