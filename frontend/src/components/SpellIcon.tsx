import { useState } from 'react'
import cleanse from '../assets/riot/spells/1.png'
import exhaust from '../assets/riot/spells/3.png'
import flash from '../assets/riot/spells/4.png'
import ghost from '../assets/riot/spells/6.png'
import heal from '../assets/riot/spells/7.png'
import smite from '../assets/riot/spells/11.png'
import teleport from '../assets/riot/spells/12.png'
import ignite from '../assets/riot/spells/14.png'
import barrier from '../assets/riot/spells/21.png'
import { spells } from '../features/automation/config'

const icons: Record<number, string> = { 1: cleanse, 3: exhaust, 4: flash, 6: ghost, 7: heal, 11: smite, 12: teleport, 14: ignite, 21: barrier }

export function SpellIcon({ id }: { id: number | null }) {
  const [failed, setFailed] = useState<string>()
  const source = id == null ? undefined : icons[id]
  const name = spells.find((spell) => spell.id === id)?.name
  return <span className="spell-art" aria-hidden="true">
    {source && source !== failed ? <img src={source} alt="" width={40} height={40} decoding="async" onError={() => setFailed(source)} />
      : <span className="spell-art__fallback">{id == null ? '+' : name?.slice(0, 2).toLocaleUpperCase('tr-TR') ?? '?'}</span>}
  </span>
}
