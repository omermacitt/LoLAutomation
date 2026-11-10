import { CheckCheck, LoaderCircle, LogOut, Save, TriangleAlert, Undo2 } from 'lucide-react'
import type { useChampionWorkspace } from '../features/champions/useChampionWorkspace'

export function SaveFooter({ workspace: w }: { workspace: ReturnType<typeof useChampionWorkspace> }) {
  const { saveState: s } = w
  const label = s.error ? 'Ayarlar kaydedilemedi' : s.saving || w.runeBusy ? 'Kaydediliyor…' : s.dirty ? 'Kaydedilmeyi bekliyor' : w.runeEditorDirty ? 'Kaydedilmemiş rün düzenlemesi' : s.saved ? 'Ayarlar güncel' : 'Seçimlerin yükleniyor'
  return <footer className="draft-footer"><div className="draft-footer__message"><span className={`draft-icon ${s.error || s.dirty ? 'draft-icon--dirty' : ''}`}>{s.error ? <TriangleAlert size={18} /> : s.saving ? <LoaderCircle size={18} className="spin" /> : <CheckCheck size={18} />}</span><div><strong role="status">{label}</strong><p>{s.error ?? (w.runeEditorDirty ? 'Rün editöründeki düzenlemeleri kaydet veya geri al.' : 'Değişikliklerin otomatik kaydedilir; çalışan otomasyona kayıttan sonra uygulanır.')}</p></div></div>
    <div className="save-actions">
      {s.conflict ? <button className="button button--secondary" disabled={s.saving || w.preparing || w.closing || w.runeBusy} onClick={() => { void w.reloadSettings() }}>Yerel değişiklikleri bırak ve yeniden yükle</button>
        : <><button className="button button--secondary" onClick={w.reset} disabled={!s.dirty || s.saving || w.preparing || w.closing || w.runeBusy}><Undo2 size={14} />Değişiklikleri geri al</button>
          <button className="button button--secondary" onClick={w.save} disabled={!s.dirty || s.saving || w.closing || w.preparing || w.runeBusy}><Save size={14} /><span>{s.error ? 'Kaydı tekrar dene' : 'Şimdi kaydet'}</span></button></>}
      <button className="button button--secondary" onClick={() => { void w.finish() }} disabled={w.ended || w.closing || w.preparing || w.runeBusy || Boolean(w.automation.busy)}><LogOut size={14} /><span>{w.closing ? 'Oturum bitiriliyor…' : 'Kaydet ve oturumu bitir'}</span></button>
    </div>
  </footer>
}
