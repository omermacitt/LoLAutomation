import { LoaderCircle, Play, Square } from 'lucide-react'
import { automationIssues, autofillWarnings, queues, roleNames } from '../features/automation/config'
import { roles } from '../features/champions/selection'
import type { RoleKey } from '../features/champions/selection'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'
import { prepareSelectionSound } from '../features/automation/selectionSound'

type Workspace = ReturnType<typeof useChampionWorkspace>
const displayRole = (name: string | null | undefined) => name && name in roleNames ? roleNames[name as RoleKey] : name ?? 'None'

export function GameControls({ workspace: w }: { workspace: Workspace }) {
  const config = w.draft
  const issues = config && w.catalog.data ? automationIssues(config, w.catalog.data) : []
  const autofill = config && w.catalog.data ? autofillWarnings(config, w.catalog.data) : []
  const running = w.automation.health?.running
  const busy = w.preparing || Boolean(w.automation.busy) || w.closing || w.runeBusy
  const selectRole = (field: 'primary_role_name' | 'secondary_role_name', label: string) => {
    const value = displayRole(config?.[field])
    return <label className="game-field"><span>{label}</span><select aria-label={label} value={value} disabled={!w.ready} onChange={(event) => w.editSettings({ [field]: event.target.value })}>
      <option value="None">Seçilmedi</option>
      {!['None', ...Object.values(roleNames)].includes(value) && <option value={value}>{value}</option>}
      {roles.map((role) => <option key={role.key} value={roleNames[role.key]}>{role.name}</option>)}
    </select></label>
  }
  return <section className="game-controls" aria-label="Otomasyon ayarları">
    <div className="game-controls__fields">
      <label className="game-field"><span>Oyun modu</span><select aria-label="Oyun modu" value={config?.queue_name ?? ''} disabled={!w.ready} onChange={(event) => w.editSettings({ queue_name: event.target.value })}>
        <option value="" disabled>Oyun modu seç</option>
        {config?.queue_name && !queues.some((queue) => queue.value === config.queue_name) && <option value={config.queue_name}>{config.queue_name}</option>}
        {queues.map((queue) => <option key={queue.id} value={queue.value}>{queue.label}</option>)}
      </select></label>
      {selectRole('primary_role_name', 'Ana rol')}{selectRole('secondary_role_name', 'İkincil rol')}
    </div>
    <div className="game-controls__actions">
      <button className="button button--primary" disabled={!w.ready || !w.health.data || running || busy || issues.length > 0 || w.saveState.conflict} onClick={() => { void prepareSelectionSound(); void w.start() }}>
        <span className="button-icon" aria-hidden="true">{w.preparing || w.automation.busy === 'starting' ? <LoaderCircle size={15} className="spin" /> : <Play size={15} />}</span>
        <span>{w.preparing ? 'Kaydediliyor…' : w.automation.busy === 'starting' ? 'Başlatılıyor…' : running ? 'Çalışıyor' : 'Otomasyonu başlat'}</span>
      </button>
      {w.automation.error && !w.actionError && running && <button className="button button--secondary" disabled={!w.ready || busy} onClick={() => { void w.apply() }}>Tekrar uygula</button>}
      <button className="button button--secondary" disabled={w.ended || w.closing || w.automation.busy === 'stopping' || (!running && w.health.data !== undefined && !busy)} onClick={() => { void w.stop() }}>
        <span className="button-icon" aria-hidden="true">{w.automation.busy === 'stopping' ? <LoaderCircle size={14} className="spin" /> : <Square size={14} />}</span><span>Durdur</span>
      </button>
    </div>
    {w.ready && issues.length > 0 && <details className="start-requirements"><summary>Başlatmak için {issues.length} seçim kaldı</summary><ul>{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul></details>}
    {w.ready && autofill.length > 0 && <p className="autofill-note">Autofill hazırlığı eksik: {autofill.join(', ')}. Bu rollere atanırsan eksik seçimleri League istemcisinde elle tamamlaman gerekebilir.</p>}
  </section>
}
