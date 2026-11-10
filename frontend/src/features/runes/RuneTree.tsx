import { useState } from 'react'
import { runeIconUrl } from '../../api/client'
import type { RuneChoice, RuneEditorCatalog, RunePage } from '../../api/contracts'
import { changePrimary, changeSecondary, chooseSecondary } from './model'

export function RuneIcon({ id, retryKey = 0 }: { id: number; retryKey?: number }) {
  const [failed, setFailed] = useState<string>()
  const key = `${id}:${retryKey}`
  return <span className="rune-icon" aria-hidden="true">{failed === key ? <span>✦</span> : <img key={key} src={runeIconUrl(id)} alt="" width={40} height={40} decoding="async" loading="lazy" onError={() => setFailed(key)} />}</span>
}

type Props = { page: RunePage; catalog: RuneEditorCatalog; disabled: boolean; onChange?: (page: RunePage) => void; retryKey?: number }
export function RuneTree({ page, catalog, disabled, onChange, retryKey = 0 }: Props) {
  const primary = catalog.styles.find((style) => style.id === page.primaryStyleId)
  const secondary = catalog.styles.find((style) => style.id === page.subStyleId)
  const selectId = (index: number, id: number) => {
    const ids = [...page.selectedPerkIds]
    ids[index] = id
    onChange?.({ ...page, selectedPerkIds: ids })
  }
  const perkButton = (perk: RuneChoice, selected: boolean, label: string, click: () => void) => <button key={perk.id} className={`rune-choice ${selected ? 'rune-choice--selected' : ''}`} aria-label={`${label}: ${perk.name}`} aria-pressed={selected} disabled={disabled} title={`${perk.name}\n${perk.description}`} onClick={click}><RuneIcon id={perk.id} retryKey={retryKey} /><span>{perk.name}</span></button>
  return <>
    <div className="rune-style-picker" aria-label="Ana yol seçimi">{catalog.styles.map((style) => <button key={style.id} className={style.id === page.primaryStyleId ? 'rune-style rune-style--active' : 'rune-style'} aria-label={`Ana yol: ${style.name}`} aria-pressed={style.id === page.primaryStyleId} disabled={disabled} title={style.description} onClick={() => onChange?.(changePrimary(page, style.id, catalog))}><RuneIcon id={style.id} retryKey={retryKey} /><span>{style.name}</span></button>)}</div>
    <div className="rune-trees">
      <section className="rune-tree rune-tree--primary" data-style={primary?.id} aria-label="Ana rün ağacı">
        <header><span className="eyebrow">ANA YOL</span><h3>{primary && <RuneIcon id={primary.id} retryKey={retryKey} />}{primary?.name ?? 'Yol seç'}</h3><p>{primary?.description ?? 'Kayıtlı rün yolu bu katalogda bulunamadı.'}</p></header>
        {primary?.rows.map((row, index) => <fieldset className={`rune-row ${index === 0 ? 'rune-row--keystone' : ''}`} key={index}><legend>{index === 0 ? 'Anahtar rün' : `${index}. satır`}</legend><div>{row.map((perk) => perkButton(perk, page.selectedPerkIds[index] === perk.id, `Ana ${index + 1}`, () => selectId(index, perk.id)))}</div></fieldset>)}
      </section>
      <section className="rune-tree rune-tree--secondary" data-style={secondary?.id} aria-label="İkincil rün ağacı">
        <header><span className="eyebrow">İKİNCİL YOL</span><h3>{secondary && <RuneIcon id={secondary.id} retryKey={retryKey} />}{secondary?.name ?? 'Yol seç'}</h3><p>İki farklı satırdan birer rün seç.</p></header>
        <div className="secondary-style-picker" aria-label="İkincil yol seçimi">{catalog.styles.map((style) => <button key={style.id} className={page.subStyleId === style.id ? 'secondary-style secondary-style--active' : 'secondary-style'} disabled={disabled || !primary?.allowedSubStyles.includes(style.id)} aria-label={`İkincil yol: ${style.name}`} aria-pressed={style.id === page.subStyleId} title={style.name} onClick={() => onChange?.(changeSecondary(page, style))}><RuneIcon id={style.id} retryKey={retryKey} /></button>)}</div>
        {secondary?.rows.slice(1).map((row, index) => <fieldset className="rune-row" key={index}><legend>{index + 1}. satır</legend><div>{row.map((perk) => perkButton(perk, page.selectedPerkIds.slice(4, 6).includes(perk.id), `İkincil ${index + 1}`, () => onChange?.(chooseSecondary(page, secondary, perk.id))))}</div></fieldset>)}
      </section>
    </div>
    <section className="rune-shards" aria-label="Nitelik parçaları"><div><span className="eyebrow">KÜÇÜK SEÇİMLER, BÜYÜK FARK</span><h3>Nitelik parçaları</h3></div>
      {primary?.shardRows.map((row, index) => <fieldset className="rune-row" key={index}><legend>{['Saldırı', 'Esneklik', 'Savunma'][index]}</legend><div>{row.map((perk) => perkButton(perk, page.selectedPerkIds[index + 6] === perk.id, `Nitelik ${index + 1}`, () => selectId(index + 6, perk.id)))}</div></fieldset>)}
    </section>
  </>
}
