import type { RuneEditorCatalog } from '../api/contracts'
import { defaultPage } from '../features/runes/model'

const choices = (ids: number[]) => ids.map((id) => ({ id, name: `Rune ${id}`, description: `Description ${id}` }))
export const runeCatalog: RuneEditorCatalog = { styles: [8000, 8100].map((id) => ({
  id, name: id === 8000 ? 'Precision' : 'Domination', description: '', allowedSubStyles: [id === 8000 ? 8100 : 8000],
  rows: [[id + 1, id + 2], [id + 11, id + 12], [id + 21], [id + 31]].map(choices),
  shardRows: [[5008, 5005, 5007], [5008, 5001, 5010], [5001, 5011, 5003]].map(choices),
})) }
export const runePage = defaultPage(runeCatalog, 'Aatrox')
