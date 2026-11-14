import type { Settings, SkinOption, SkinOptions } from '../../api/contracts'
import type { RoleKey } from '../champions/selection'

export type SkinFamily = { skin: SkinOption; chromas: SkinOption[] }

export function skinFamilies(options: SkinOptions | undefined): SkinFamily[] {
  return options?.skins.filter((skin) => skin.parent_skin_id === undefined)
    .map((skin) => ({ skin, chromas: options.skins.filter((item) => item.parent_skin_id === skin.id) })) ?? []
}

export function selectedSkin(config: Settings | undefined, role: RoleKey, championId: number): number | undefined {
  const entries = config?.custom_skins[role]
  const raw = entries && typeof entries === 'object' ? (entries as Record<string, unknown>)[String(championId)] : undefined
  if (raw === undefined) return championId * 1000
  return typeof raw === 'number' && Number.isSafeInteger(raw) && raw > 0 ? raw : undefined
}

export function withSkin(config: Settings, role: RoleKey, championId: number, skinId: number, options: SkinOptions): Settings {
  if (options.champion_id !== championId || !options.skins.some((skin) => skin.id === skinId)
    || Math.floor(skinId / 1000) !== championId) return config
  const next = structuredClone(config)
  const entries = next.custom_skins[role]
  const skins = entries && typeof entries === 'object' && !Array.isArray(entries) ? { ...entries as Record<string, unknown> } : {}
  if (skinId === championId * 1000) delete skins[String(championId)]
  else skins[String(championId)] = skinId
  if (Object.keys(skins).length) next.custom_skins[role] = skins
  else delete next.custom_skins[role]
  return next
}
