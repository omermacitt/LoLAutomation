import { Zap } from 'lucide-react'
import { spells } from '../features/automation/config'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'

export function SpellEditor({ workspace: w }: { workspace: ReturnType<typeof useChampionWorkspace> }) {
  if (w.target.kind !== 'pick') return null
  const id = w.draft?.role_champions_ui[w.role]?.[w.target.index]
  const pair = id == null ? undefined : w.draft?.custom_summoner_spells[w.role]?.[String(id)]
  const available = id != null && w.catalog.data?.pickable_champions.some((champion) => champion.id === id)
  return <div className="spell-editor"><h4><Zap size={13} />{w.target.index + 1}. tercih büyüleri</h4><div>
    {(['spell1Id', 'spell2Id'] as const).map((slot, index) => {
      const value = pair?.[slot] ?? null
      const other = pair?.[slot === 'spell1Id' ? 'spell2Id' : 'spell1Id']
      return <label key={slot}><span>{index === 0 ? 'Birinci büyü' : 'İkinci büyü'}</span><select aria-label={index === 0 ? 'Birinci büyü' : 'İkinci büyü'} value={value ?? ''} disabled={!w.ready || !available} onChange={(event) => w.changeSpell(slot, event.target.value === '' ? null : Number(event.target.value))}>
        <option value="">Seçilmedi</option>
        {value !== null && !spells.some((spell) => spell.id === value) && <option value={value}>Büyü #{value}</option>}
        {spells.map((spell) => <option key={spell.id} value={spell.id} disabled={spell.id === other}>{spell.name}</option>)}
      </select></label>
    })}
  </div></div>
}
