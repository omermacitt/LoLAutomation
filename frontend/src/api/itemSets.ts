import { z } from 'zod'

export const itemStatsSchema = z.object({ ad: z.number(), ap: z.number(), hp: z.number(), armor: z.number(), mr: z.number(), attack_speed: z.number(), haste: z.number() })
export const builderItemSchema = z.object({ id: z.number().int().positive(), name: z.string(), price: z.number().nonnegative(), stats: itemStatsSchema, tags: z.array(z.string()), description: z.string() })
export const itemCatalogSchema = z.object({ version: z.string(), champions: z.array(z.object({ id: z.number().int().positive(), name: z.string() })), items: z.array(builderItemSchema) })
export const championItemStatsSchema = z.object({ champion_id: z.number().int().positive(), version: z.string(), base: itemStatsSchema, growth: itemStatsSchema, attack_speed_ratio: z.number().positive() })
export const itemSetSchema = z.object({ uid: z.string(), title: z.string().min(1).max(60), champion_id: z.number().int().positive().nullable(), map_id: z.literal(11), blocks: z.array(z.object({ name: z.string().min(1).max(60), items: z.array(z.object({ id: z.number().int().positive(), count: z.number().int().min(1).max(10) })), slots: z.array(z.number().int().positive().nullable()).length(6).nullable().optional() })).min(1).max(20) })
export const itemSetCollectionSchema = z.object({ sets: z.array(itemSetSchema).max(100) })
export const itemClientStateSchema = z.object({ revision: z.string(), set_count: z.number().int().nonnegative() })
export type ItemStats = z.infer<typeof itemStatsSchema>
export type BuilderItem = z.infer<typeof builderItemSchema>
export type ItemCatalog = z.infer<typeof itemCatalogSchema>
export type ChampionItemStats = z.infer<typeof championItemStatsSchema>
export type ItemSet = z.infer<typeof itemSetSchema>
export type ItemSetCollection = z.infer<typeof itemSetCollectionSchema>
export type ItemClientState = z.infer<typeof itemClientStateSchema>

export interface ItemSetApi {
  itemCatalog(signal: AbortSignal): Promise<ItemCatalog>
  itemChampion(id: number, signal: AbortSignal): Promise<ChampionItemStats>
  itemSets(signal: AbortSignal): Promise<ItemSetCollection>
  saveItemSets(collection: ItemSetCollection): Promise<ItemSetCollection>
  itemClientState(signal: AbortSignal): Promise<ItemClientState>
  exportItemSet(uid: string, revision: string): Promise<ItemClientState>
}
