import { useState } from 'react'
import { runeIconUrl } from '../../api/client'
import type { RuneChoice, RuneEditorCatalog, RunePage } from '../../api/contracts'
import { changePrimary, changeSecondary, chooseSecondary } from './model'

export function RuneIcon({ id, retryKey = 0 }: { id: number; retryKey?: number }) {
  const [failed, setFailed] = useState<string>()
  const key = `${id}:${retryKey}`
  return <span className="rune-icon" aria-hidden="true">{failed === key ? <span>✦</span> : <img key={key} src={runeIconUrl(id)} alt="" width={40} height={40} decoding="async" loading="lazy" onError={() => setFailed(key)} />}</span>
}

type Props = { page: RunePage; catalog: RuneEditorCatalog; disabled: boolean; readOnly?: boolean; onChange?: (page: RunePage) => void; retryKey?: number }
export function RuneTree({ page, catalog, disabled, readOnly = false, onChange, retryKey = 0 }: Props) {
  const primary = catalog.styles.find((style) => style.id === page.primaryStyleId)
  const secondary = catalog.styles.find((style) => style.id === page.subStyleId)
  const update = (next: RunePage) => { if (!disabled && !readOnly) onChange?.(next) }
  const selectId = (index: number, id: number) => {
    const ids = [...page.selectedPerkIds]
    ids[index] = id
    update({ ...page, selectedPerkIds: ids })
  }
  const perkButton = (perk: RuneChoice, selected: boolean, label: string, click: () => void) => <button key={perk.id} className={`rune-choice ${selected ? 'rune-choice--selected' : ''}`} aria-label={`${label}: ${perk.name}`} aria-description={perk.description} aria-pressed={selected} aria-disabled={disabled || readOnly} disabled={disabled} title={perk.name} onClick={click}><RuneIcon id={perk.id} retryKey={retryKey} /><span className="rune-choice__tooltip" aria-hidden="true"><strong>{perk.name}</strong><span>{perk.description}</span></span></button>
  return <div className="rune-trees">
      <section className="rune-tree rune-tree--primary" data-style={primary?.id} aria-label="Ana rün ağacı">
        <header><h3>{primary?.name ?? 'Yol seç'}</h3><span>Ana yol</span></header>
        <div className="rune-style-picker" aria-label="Ana yol seçimi">{catalog.styles.map((style) => <button key={style.id} className={style.id === page.primaryStyleId ? 'rune-style rune-style--active' : 'rune-style'} aria-label={`Ana yol: ${style.name}`} aria-pressed={style.id === page.primaryStyleId} aria-disabled={disabled || readOnly} disabled={disabled} title={style.name} onClick={() => update(changePrimary(page, style.id, catalog))}><RuneIcon id={style.id} retryKey={retryKey} /></button>)}</div>
        {primary?.rows.map((row, index) => <fieldset className={`rune-row ${index === 0 ? 'rune-row--keystone' : ''}`} key={index}><legend>{index === 0 ? 'Anahtar rün' : `${index}. satır`}</legend><div>{row.map((perk) => perkButton(perk, page.selectedPerkIds[index] === perk.id, `Ana ${index + 1}`, () => selectId(index, perk.id)))}</div></fieldset>)}
      </section>
      <section className="rune-tree rune-tree--secondary" data-style={secondary?.id} aria-label="İkincil rün ağacı">
        <header><h3>{secondary?.name ?? 'Yol seç'}</h3><span>İkincil yol · İki farklı satır</span></header>
        <div className="secondary-style-picker" aria-label="İkincil yol seçimi">{catalog.styles.map((style) => <button key={style.id} className={page.subStyleId === style.id ? 'secondary-style secondary-style--active' : 'secondary-style'} aria-disabled={disabled || readOnly || !primary?.allowedSubStyles.includes(style.id)} disabled={disabled || !primary?.allowedSubStyles.includes(style.id)} aria-label={`İkincil yol: ${style.name}`} aria-pressed={style.id === page.subStyleId} title={style.name} onClick={() => update(changeSecondary(page, style))}><RuneIcon id={style.id} retryKey={retryKey} /></button>)}</div>
        {secondary?.rows.slice(1).map((row, index) => <fieldset className="rune-row" key={index}><legend>{index + 1}. satır</legend><div>{row.map((perk) => perkButton(perk, page.selectedPerkIds.slice(4, 6).includes(perk.id), `İkincil ${index + 1}`, () => update(chooseSecondary(page, secondary, perk.id))))}</div></fieldset>)}
    <section className="rune-shards" aria-label="Nitelik parçaları"><h4>Nitelik parçaları</h4>
      {primary?.shardRows.map((row, index) => <fieldset className="rune-row" key={index}><legend>{['Saldırı', 'Esneklik', 'Savunma'][index]}</legend><div>{row.map((perk) => perkButton(perk, page.selectedPerkIds[index + 6] === perk.id, `Nitelik ${index + 1}`, () => selectId(index + 6, perk.id)))}</div></fieldset>)}
    </section>
      </section>
    </div>
}
