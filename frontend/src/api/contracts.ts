import { z } from 'zod'

// Wire shapes match the existing FastAPI response models. Migration remains a
// backend responsibility; a malformed response must not become empty defaults.
const championSchema = z.object({ id: z.number().int().positive(), name: z.string().min(1) })
const spellPairSchema = z.object({ spell1Id: z.number().int().nullable(), spell2Id: z.number().int().nullable() }).passthrough()
export const catalogSchema = z.object({
  all_champions: z.array(championSchema).min(1),
  pickable_champions: z.array(championSchema),
})
export const healthSchema = z.object({
  status: z.literal('ok'), running: z.boolean(), version: z.string(),
  selection: z.object({ id: z.number().int().positive(),
    code: z.enum(['no_preference', 'all_unavailable', 'pick_failed', 'manual_hover']),
    role: z.string(), champion_id: z.number().int().positive().nullable(),
  }).nullable().optional(),
})
export type SelectionNotice = NonNullable<z.infer<typeof healthSchema>['selection']>
export const settingsSchema = z.object({
  queue_name: z.string().nullable(),
  primary_role_name: z.string().nullable(),
  secondary_role_name: z.string().nullable(),
  role_champions_ui: z.record(z.string(), z.array(z.number().int().positive().nullable())),
  role_bans_ui: z.record(z.string(), z.number().int().positive().nullable()),
  custom_runes: z.record(z.string(), z.unknown()),
  rune_selection: z.record(z.string(), z.number().int()),
  custom_skins: z.record(z.string(), z.unknown()),
  custom_summoner_spells: z.record(z.string(), z.record(z.string(), spellPairSchema)),
}).passthrough()

export const automationSchema = z.object({
  primary_role: z.string().nullable(), secondary_role: z.string().nullable(),
  primary_summoner_spell: z.number().int().nullable(), secondary_summoner_spell: z.number().int().nullable(),
  role_summoner_spells: z.record(z.string(), spellPairSchema),
  custom_summoner_spells: settingsSchema.shape.custom_summoner_spells,
  queue_id: z.number().int(),
  role_champions: z.record(z.string(), z.array(z.number().int().positive())),
  role_bans: z.record(z.string(), z.number().int().positive()),
  custom_runes: settingsSchema.shape.custom_runes,
  rune_selection: settingsSchema.shape.rune_selection,
  custom_skins: settingsSchema.shape.custom_skins,
  auto_queue: z.boolean(),
})
export const startResultSchema = z.object({ status: z.enum(['started', 'updated']), config: automationSchema })
export const stopResultSchema = z.object({ status: z.literal('stopped') })
export type AutomationConfig = z.infer<typeof automationSchema>
export type StartResult = z.infer<typeof startResultSchema>

export const runePageSchema = z.object({ name: z.string(), primaryStyleId: z.number().int().positive(), subStyleId: z.number().int().positive(), selectedPerkIds: z.array(z.number().int().positive()).length(9) })
const runeChoiceSchema = z.object({ id: z.number().int().positive(), name: z.string(), description: z.string() })
export const runeEditorCatalogSchema = z.object({ styles: z.array(z.object({
  id: z.number().int().positive(), name: z.string(), description: z.string(), allowedSubStyles: z.array(z.number().int().positive()),
  rows: z.array(z.array(runeChoiceSchema).min(1)).length(4), shardRows: z.array(z.array(runeChoiceSchema).min(1)).length(3),
})).min(2) })
export const runeRecommendationSchema = z.object({ champion_id: z.number().int().positive(), source: z.literal('bundled'), page: runePageSchema.nullable(), unavailableReason: z.enum(['missing', 'outdated']).nullable() })
export type RunePage = z.infer<typeof runePageSchema>
export type RuneChoice = z.infer<typeof runeChoiceSchema>
export type RuneEditorCatalog = z.infer<typeof runeEditorCatalogSchema>
export type RuneStyle = RuneEditorCatalog['styles'][number]
export type RuneRecommendation = z.infer<typeof runeRecommendationSchema>

export const skinOptionsSchema = z.object({ champion_id: z.number().int().positive(),
  skins: z.array(z.object({ id: z.number().int().positive(), name: z.string().min(1) })).min(1),
}).superRefine((value, context) => {
  if (value.skins.some((skin) => Math.floor(skin.id / 1000) !== value.champion_id)
    || new Set(value.skins.map((skin) => skin.id)).size !== value.skins.length
    || !value.skins.some((skin) => skin.id === value.champion_id * 1000)) {
    context.addIssue({ code: 'custom', message: 'Skin options do not match the champion' })
  }
})
export type SkinOptions = z.infer<typeof skinOptionsSchema>
export type SkinOption = SkinOptions['skins'][number]

export type Champion = z.infer<typeof championSchema>
export type ChampionCatalog = z.infer<typeof catalogSchema>
export type Health = z.infer<typeof healthSchema>
export type Settings = z.infer<typeof settingsSchema>

export interface PilotApi {
  health(signal: AbortSignal): Promise<Health>
  settings(signal: AbortSignal): Promise<Settings>
  champions(signal: AbortSignal): Promise<ChampionCatalog>
  saveSettings(config: Settings): Promise<Settings>
  start(config: AutomationConfig): Promise<StartResult>
  update(config: AutomationConfig): Promise<StartResult>
  stop(): Promise<void>
  runeCatalog(signal: AbortSignal): Promise<RuneEditorCatalog>
  recommendedRune(championId: number, signal: AbortSignal): Promise<RuneRecommendation>
  validateRune(page: RunePage): Promise<RunePage>
  skins(championId: number, signal: AbortSignal): Promise<SkinOptions>
}
