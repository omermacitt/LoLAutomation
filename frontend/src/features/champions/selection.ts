import type { Champion, ChampionCatalog, Settings } from '../../api/contracts'

export const roles = [
  { key: 'TOP', name: 'Üst koridor', short: 'TOP' },
  { key: 'JUNGLE', name: 'Orman', short: 'JNG' },
  { key: 'MIDDLE', name: 'Orta koridor', short: 'MID' },
  { key: 'BOTTOM', name: 'Alt koridor', short: 'ADC' },
  { key: 'UTILITY', name: 'Destek', short: 'SUP' },
] as const
export type RoleKey = typeof roles[number]['key']
export type Target = { kind: 'pick'; index: number } | { kind: 'ban' }
export type Selection = Pick<Settings, 'role_champions_ui' | 'role_bans_ui'>

export function initialRole(settings: Settings): RoleKey {
  const aliases: Record<string, RoleKey> = {
    Top: 'TOP', Jungle: 'JUNGLE', Mid: 'MIDDLE', ADC: 'BOTTOM', Support: 'UTILITY',
  }
  const name = settings.primary_role_name ?? ''
  return roles.find((role) => role.key === name)?.key ?? aliases[name] ?? 'TOP'
}

export function copySelection(settings: Selection): Selection {
  return {
    role_champions_ui: Object.fromEntries(Object.entries(settings.role_champions_ui).map(([role, ids]) => [role, [...ids]])),
    role_bans_ui: { ...settings.role_bans_ui },
  }
}

export function updateSelection(selection: Selection, role: RoleKey, target: Target, id: number | null): Selection {
  if (target.kind === 'pick' && id !== null && siblingPickIndex(selection, role, target.index, id) !== undefined) return selection
  const next = copySelection(selection)
  if (target.kind === 'ban') next.role_bans_ui[role] = id
  else {
    const picks = [...(next.role_champions_ui[role] ?? [])]
    while (picks.length < 3) picks.push(null)
    picks[target.index] = id
    next.role_champions_ui[role] = picks
  }
  return next
}

export function siblingPickIndex(selection: Selection | undefined, role: RoleKey, index: number, id: number): number | undefined {
  const found = selection?.role_champions_ui[role]?.findIndex((chosen, slot) => slot !== index && chosen === id) ?? -1
  return found < 0 ? undefined : found
}

export function resolveChampion(catalog: ChampionCatalog | undefined, id: number | null): Champion | undefined {
  return id === null ? undefined : catalog?.all_champions.find((champion) => champion.id === id)
}

export function initials(name: string): string {
  return name.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 2).toLocaleUpperCase('tr')
}
