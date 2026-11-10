import { ArrowDown, ArrowUp, ChevronRight, Crosshair } from 'lucide-react'
import { ChampionArtwork } from './ChampionArtwork'
import { resolveChampion } from '../features/champions/selection'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'

const labels = ['İlk tercih', 'İkinci tercih', 'Üçüncü tercih']
export function PriorityPicks({ workspace: w }: { workspace: ReturnType<typeof useChampionWorkspace> }) {
  const pickable = new Set(w.catalog.data?.pickable_champions.map((champion) => champion.id))
  return <div className="priority-list">{[0, 1, 2].map((index) => {
    const id = w.draft?.role_champions_ui[w.role]?.[index] ?? null
    const champion = resolveChampion(w.catalog.data, id)
    const name = champion?.name ?? (id !== null ? `Şampiyon #${id}` : 'Şampiyon seç')
    const active = w.target.kind === 'pick' && w.target.index === index
    return <div key={index}><div className="priority-row">
      <button className={`priority-slot ${active ? 'priority-slot--active' : ''}`} aria-label={`${index + 1}. tercih: ${name}`} aria-pressed={active} disabled={!w.ready} onClick={() => w.setTarget({ kind: 'pick', index })}>
        <span className="priority-slot__number">0{index + 1}</span>
        {id !== null ? <ChampionArtwork id={id} name={name} small retryKey={w.portraitRetryKey} /> : <span className="priority-slot__empty"><Crosshair size={18} /></span>}
        <span className="priority-slot__text"><small>{labels[index]}</small><strong>{name}</strong>{id !== null && !pickable.has(id) && <em>Şu anda seçilemiyor</em>}</span>
        {active ? <span className="priority-slot__active-dot" /> : <ChevronRight size={14} />}
      </button>
      <div className="reorder-actions"><button aria-label={`${index + 1}. tercihi yukarı taşı`} disabled={!w.ready || index === 0} onClick={() => w.reorder(index, -1)}><ArrowUp size={12} /></button><button aria-label={`${index + 1}. tercihi aşağı taşı`} disabled={!w.ready || index === 2} onClick={() => w.reorder(index, 1)}><ArrowDown size={12} /></button></div>
    </div>{index < 2 && <span className="priority-arrow"><ArrowDown size={12} /></span>}</div>
  })}</div>
}
