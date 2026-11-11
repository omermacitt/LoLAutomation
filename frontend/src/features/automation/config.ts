import type { AutomationConfig, ChampionCatalog, Settings } from '../../api/contracts'
import { roles } from '../champions/selection'
import type { RoleKey, Target } from '../champions/selection'
import { siblingPickIndex, updateSelection } from '../champions/selection'

export const queues = [
  { value: 'Normal Draft', label: 'Normal Sıralı', id: 400 },
  { value: 'Ranked Solo/Duo', label: 'Dereceli Tek/Çift', id: 420 },
  { value: 'Ranked Flex', label: 'Dereceli Esnek', id: 440 },
] as const
export const roleNames: Record<RoleKey, string> = { TOP: 'Top', JUNGLE: 'Jungle', MIDDLE: 'Mid', BOTTOM: 'ADC', UTILITY: 'Support' }
export const spells = [
  { id: 4, name: 'Sıçra' }, { id: 14, name: 'Tutuştur' }, { id: 12, name: 'Işınlan' },
  { id: 6, name: 'Hayalet' }, { id: 7, name: 'Şifa' }, { id: 11, name: 'Çarp' },
  { id: 3, name: 'Bitkinlik' }, { id: 21, name: 'Bariyer' }, { id: 1, name: 'Arındır' },
] as const
export const roleKey = (name: string | null) => roles.find((role) => role.key === name || roleNames[role.key] === name)?.key ?? null

export function selectChampion(config: Settings, role: RoleKey, target: Target, id: number | null): Settings {
  if (target.kind === 'pick' && id !== null && siblingPickIndex(config, role, target.index, id) !== undefined) return config
  const result = { ...config, ...updateSelection(config, role, target, id) }
  if (id !== null && target.kind === 'pick') {
    const current = result.custom_skins[role]
    if (current && typeof current === 'object' && String(id) in current) return result
    for (const value of Object.values(result.custom_skins)) {
      if (!value || typeof value !== 'object') continue
      const skin = (value as Record<string, unknown>)[String(id)]
      if (typeof skin === 'number') {
        result.custom_skins = { ...result.custom_skins, [role]: { ...(current as object ?? {}), [String(id)]: skin } }
        break
      }
    }
  }
  return result
}

export function setSpell(config: Settings, role: RoleKey, id: number, slot: 'spell1Id' | 'spell2Id', spell: number | null): Settings {
  const previous = config.custom_summoner_spells[role]?.[String(id)] ?? { spell1Id: null, spell2Id: null }
  const pair = { ...previous, [slot]: spell }
  if (spell !== null && pair.spell1Id === pair.spell2Id) pair[slot === 'spell1Id' ? 'spell2Id' : 'spell1Id'] = null
  return { ...config, custom_summoner_spells: { ...config.custom_summoner_spells,
    [role]: { ...config.custom_summoner_spells[role], [String(id)]: pair } } }
}

export function movePick(config: Settings, role: RoleKey, index: number, step: -1 | 1): Settings {
  const next = index + step
  if (index < 0 || index > 2 || next < 0 || next > 2) return config
  const picks = [...(config.role_champions_ui[role] ?? [])]
  while (picks.length < 3) picks.push(null)
  ;[picks[index], picks[next]] = [picks[next], picks[index]]
  return { ...config, role_champions_ui: { ...config.role_champions_ui, [role]: picks } }
}

export function automationIssues(config: Settings, catalog: ChampionCatalog): string[] {
  const pickable = new Set(catalog.pickable_champions.map((champion) => champion.id))
  const all = new Set(catalog.all_champions.map((champion) => champion.id))
  const issues: string[] = []
  const required = new Set([roleKey(config.primary_role_name), roleKey(config.secondary_role_name)].filter(Boolean))
  if (!queues.some((queue) => queue.value === config.queue_name)) issues.push('Bir oyun modu seç.')
  if (roleKey(config.primary_role_name) !== null && roleKey(config.primary_role_name) === roleKey(config.secondary_role_name)) issues.push('Ana ve ikincil roller farklı olmalı.')
  for (const role of roles) {
    if (required.size && !required.has(role.key)) continue
    if (!config.role_champions_ui[role.key]?.some((id) => id !== null && pickable.has(id))) issues.push(`${role.name}: en az bir seçilebilir şampiyon belirle.`)
    const ban = config.role_bans_ui[role.key]
    if (ban == null || !all.has(ban)) issues.push(`${role.name}: yasaklanacak bir şampiyon belirle.`)
  }
  return issues
}

export function autofillWarnings(config: Settings, catalog: ChampionCatalog): string[] {
  const preferred = new Set([roleKey(config.primary_role_name), roleKey(config.secondary_role_name)].filter(Boolean))
  const pickable = new Set(catalog.pickable_champions.map((champion) => champion.id))
  const known = new Set(catalog.all_champions.map((champion) => champion.id))
  return roles.filter((role) => !preferred.has(role.key) && (
    !config.role_champions_ui[role.key]?.some((id) => id !== null && pickable.has(id))
    || !known.has(config.role_bans_ui[role.key] ?? 0)
  )).map((role) => role.name)
}

export function automationPayload(config: Settings, catalog: ChampionCatalog): AutomationConfig {
  const primary = roleKey(config.primary_role_name)
  const pickable = new Set(catalog.pickable_champions.map((champion) => champion.id))
  const all = new Set(catalog.all_champions.map((champion) => champion.id))
  const roleChampions: Record<string, number[]> = {}
  const roleBans: Record<string, number> = {}
  const roleSpells: AutomationConfig['role_summoner_spells'] = {}
  for (const role of roles) {
    const picks = [...new Set((config.role_champions_ui[role.key] ?? []).filter((id): id is number => id !== null && pickable.has(id)))]
    if (picks.length) {
      roleChampions[role.key] = picks
      const pair = config.custom_summoner_spells[role.key]?.[String(picks[0])]
      if (pair) roleSpells[role.key] = pair
    }
    const ban = config.role_bans_ui[role.key]
    if (ban != null && all.has(ban)) roleBans[role.key] = ban
  }
  return {
    queue_id: queues.find((queue) => queue.value === config.queue_name)?.id ?? 420,
    primary_role: primary, secondary_role: roleKey(config.secondary_role_name),
    primary_summoner_spell: roleSpells[primary ?? '']?.spell1Id ?? null,
    secondary_summoner_spell: roleSpells[primary ?? '']?.spell2Id ?? null,
    role_summoner_spells: roleSpells, role_champions: roleChampions, role_bans: roleBans,
    custom_summoner_spells: config.custom_summoner_spells, custom_runes: config.custom_runes,
    rune_selection: config.rune_selection, role_rune_selection: config.role_rune_selection, custom_skins: config.custom_skins, auto_queue: true,
  }
}
