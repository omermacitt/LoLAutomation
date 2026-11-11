import type { ChampionCatalog, Health, Settings } from '../api/contracts'

export const health: Health = { status: 'ok', running: false, version: 'test' }
export const catalog: ChampionCatalog = {
  all_champions: [
    { id: 266, name: 'Aatrox' }, { id: 103, name: 'Ahri' }, { id: 84, name: 'Akali' },
    { id: 12, name: 'Alistar' }, { id: 32, name: 'Amumu' }, { id: 34, name: 'Anivia' },
    { id: 1, name: 'Annie' }, { id: 22, name: 'Ashe' }, { id: 136, name: 'Aurelion Sol' },
    { id: 268, name: 'Azir' }, { id: 432, name: 'Bard' }, { id: 53, name: 'Blitzcrank' },
    { id: 63, name: 'Brand' }, { id: 201, name: 'Braum' }, { id: 51, name: 'Caitlyn' },
    { id: 164, name: 'Camille' }, { id: 69, name: 'Cassiopeia' }, { id: 31, name: "Cho'Gath" },
    { id: 122, name: 'Darius' }, { id: 131, name: 'Diana' }, { id: 119, name: 'Draven' },
    { id: 245, name: 'Ekko' }, { id: 60, name: 'Elise' }, { id: 28, name: 'Evelynn' },
    { id: 81, name: 'Ezreal' }, { id: 114, name: 'Fiora' }, { id: 105, name: 'Fizz' },
    { id: 3, name: 'Galio' }, { id: 86, name: 'Garen' }, { id: 150, name: 'Gnar' },
  ],
  pickable_champions: [],
}
catalog.pickable_champions = catalog.all_champions.filter((champion) => champion.id !== 84)

export const settings: Settings = {
  queue_name: 'Ranked Solo/Duo', primary_role_name: 'Top', secondary_role_name: 'Mid',
  role_champions_ui: { TOP: [266, 86, 122], MIDDLE: [103, null, null] },
  role_bans_ui: { TOP: 84 }, custom_runes: {}, rune_selection: {}, custom_skins: {},
  custom_summoner_spells: {}, role_rune_selection: {},
}

export function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => { resolve = resolvePromise; reject = rejectPromise })
  return { promise, resolve, reject }
}
