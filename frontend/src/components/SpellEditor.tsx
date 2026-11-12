import { useEffect, useId, useRef, useState } from 'react'
import { Check, ChevronDown, X, Zap } from 'lucide-react'
import { spells } from '../features/automation/config'
import { roles } from '../features/champions/selection'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'
import { SpellIcon } from './SpellIcon'
import './SpellEditor.css'

type Slot = 'spell1Id' | 'spell2Id'
type Pair = { spell1Id?: number | null; spell2Id?: number | null }
const slotName = (slot: Slot) => slot === 'spell1Id' ? 'Birinci büyü' : 'İkinci büyü'
const spellName = (id: number | null | undefined) => spells.find((spell) => spell.id === id)?.name
  ?? (id == null ? 'Seçilmedi' : `Büyü #${id}`)

export function SpellEditor({ workspace: w }: { workspace: ReturnType<typeof useChampionWorkspace> }) {
  if (w.target.kind !== 'pick') return null
  const id = w.draft?.role_champions_ui[w.role]?.[w.target.index]
  const pair = id == null ? undefined : w.draft?.custom_summoner_spells[w.role]?.[String(id)]
  const available = id != null && w.catalog.data?.pickable_champions.some((champion) => champion.id === id)
  const champion = w.catalog.data?.all_champions.find((item) => item.id === id)
  // Changing role, preference or champion removes any open picker for the old target.
  return <SpellPicker key={`${w.role}:${w.target.index}:${id}`} pair={pair}
    disabled={!w.ready || !available} preference={w.target.index + 1}
    context={`${roles.find((role) => role.key === w.role)?.name ?? w.role} · ${champion?.name ?? 'Şampiyon seçilmedi'}`}
    onChange={w.changeSpell} />
}

function SpellPicker({ pair, disabled, preference, context, onChange }: {
  pair?: Pair; disabled: boolean; preference: number; context: string;
  onChange: (slot: Slot, spell: number | null) => void;
}) {
  const [active, setActive] = useState<Slot | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const opener = useRef<HTMLButtonElement | null>(null)
  const titleId = useId()
  const descriptionId = useId()
  const current = active ? pair?.[active] ?? null : null
  const other = active ? pair?.[active === 'spell1Id' ? 'spell2Id' : 'spell1Id'] ?? null : null

  useEffect(() => {
    const element = dialog.current
    if (!element) return
    if (disabled && active) setActive(null)
    if (active && !disabled) {
      if (!element.open) {
        element.showModal()
        const selected = element.querySelector<HTMLButtonElement>(`[data-spell="${current}"]:not(:disabled)`)
        const first = element.querySelector<HTMLButtonElement>('[data-spell]:not(:disabled)')
        const focusTarget = selected ?? first
        focusTarget?.focus()
      }
    } else if (element.open) element.close()
  }, [active, disabled, current])

  const choose = (value: number | null) => {
    if (!active || disabled || (value !== null && value === other)) return
    onChange(active, value)
    setActive(null)
  }

  return <section className="spell-editor" aria-label="Büyü seçimi">
    <h4><Zap size={13} aria-hidden="true" />{preference}. tercih büyüleri</h4>
    <div className="spell-slots">
      {(['spell1Id', 'spell2Id'] as const).map((slot) => {
        const value = pair?.[slot] ?? null
        return <div className="spell-slot" key={slot}>
          <span className="spell-slot__label">{slotName(slot)}</span>
          <button className="spell-slot__button" aria-label={`${slotName(slot)}: ${spellName(value)}`}
            aria-haspopup="dialog" disabled={disabled} title={`${slotName(slot)}: ${spellName(value)}`}
            onClick={(event) => { opener.current = event.currentTarget; setActive(slot) }}>
            <SpellIcon id={value} />
            <span className="spell-slot__name">{spellName(value)}</span>
            <ChevronDown size={12} aria-hidden="true" />
          </button>
        </div>
      })}
    </div>
    <dialog ref={dialog} className="spell-picker" aria-labelledby={titleId} aria-describedby={descriptionId}
      onKeyDown={(event) => {
        if (event.key !== 'Tab' || event.ctrlKey || event.altKey || event.metaKey) return
        const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
        const first = buttons[0]
        const last = buttons[buttons.length - 1]
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last?.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus()
        }
      }}
      onClose={(event) => {
        if (event.currentTarget.open) return
        setActive(null)
        if (opener.current?.isConnected && !opener.current.disabled) opener.current.focus()
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget) return
        const box = event.currentTarget.getBoundingClientRect()
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) setActive(null)
      }}>
      <header className="spell-picker__header">
        <div><h2 id={titleId}>{active ? slotName(active) : 'Büyü'} seçimi</h2>
          <p id={descriptionId}>{context} · {preference}. tercih</p></div>
        <button className="spell-picker__close" aria-label="Büyü seçimini kapat" onClick={() => setActive(null)}><X size={18} aria-hidden="true" /></button>
      </header>
      <div className="spell-picker__grid" aria-label="Kullanılabilir büyüler">
        {spells.map((spell) => <button key={spell.id} data-spell={spell.id}
          className={`spell-choice ${current === spell.id ? 'spell-choice--selected' : ''}`}
          aria-label={spell.name} aria-pressed={current === spell.id} disabled={disabled || other === spell.id}
          title={other === spell.id ? `${spell.name} diğer büyü slotunda seçili` : spell.name}
          onClick={() => choose(spell.id)}>
          <SpellIcon id={spell.id} /><span>{spell.name}</span>
          {current === spell.id && <Check className="spell-choice__check" size={14} aria-hidden="true" />}
        </button>)}
      </div>
      <p className="spell-picker__hint">{other == null ? 'Bu slot için bir büyü seç.' : `${spellName(other)} diğer büyü slotunda seçili.`}</p>
      <footer className="spell-picker__footer">
        <button className="button button--secondary" disabled={disabled || current == null} onClick={() => choose(null)}>Bu slotu temizle</button>
        <button className="button button--secondary" onClick={() => setActive(null)}>Vazgeç</button>
      </footer>
    </dialog>
  </section>
}
