import { useEffect, useRef, useState } from 'react'
import { TriangleAlert, Volume2, VolumeX } from 'lucide-react'
import type { Health, SelectionNotice } from '../api/contracts'
import { roles } from '../features/champions/selection'
import { playSelectionSound, stopSelectionSound } from '../features/automation/selectionSound'

export function SelectionAlert({ health, onStop, stopping }: { health?: Health; onStop: () => void; stopping: boolean }) {
  const previous = useRef<SelectionNotice | null>(null)
  if (health) previous.current = health.running ? health.selection ?? null : null
  const notice = health ? health.running ? health.selection : undefined : previous.current
  const [muted, setMuted] = useState(false)
  const [soundBlocked, setSoundBlocked] = useState(false)
  const last = useRef<string | undefined>(undefined)
  const alive = useRef(true)
  useEffect(() => { alive.current = true; return () => { alive.current = false; stopSelectionSound() } }, [])
  const key = notice ? `${notice.id}:${notice.code}:${notice.role}` : undefined
  const current = useRef({ key, muted, stopping })
  const audioEpoch = useRef(0)
  if (current.current.key !== key || current.current.muted !== muted || current.current.stopping !== stopping) audioEpoch.current++
  current.current = { key, muted, stopping }
  const sound = async () => {
    const requested = key
    const epoch = audioEpoch.current
    const valid = () => alive.current && audioEpoch.current === epoch && current.current.key === requested && !current.current.muted && !current.current.stopping
    const played = await playSelectionSound(valid)
    if (valid()) setSoundBlocked(!played)
  }
  useEffect(() => { if (!key || muted || stopping) stopSelectionSound() }, [key, muted, stopping])
  useEffect(() => {
    if (!notice || !key || last.current === key) return
    last.current = key
    setSoundBlocked(false)
    if (!muted && notice.code !== 'manual_hover') void sound()
  }, [key, notice, muted])
  if (!notice) return null
  const role = roles.find((item) => item.key === notice.role)?.name ?? 'Atanan rol'
  const title = notice.code === 'no_preference' ? `${role} için şampiyon tercihi yok`
    : notice.code === 'all_unavailable' ? `${role} için uygun şampiyon kalmadı`
      : notice.code === 'pick_failed' ? `${role} için otomatik seçim tamamlanamadı` : 'Manuel şampiyon seçimi algılandı'
  return <section className="selection-alert" aria-label="Manuel seçim bildirimi">
    <TriangleAlert size={22} aria-hidden="true" />
    <div className="selection-alert__content"><div role="alert"><strong>{title}</strong>
      {notice.code === 'all_unavailable' && <p>Tercihlerin banlı, alınmış veya şu anda seçilemiyor.</p>}
      <p>League istemcisine geç, şampiyonunu seç ve kilitle. Bu seçim turu sana bırakıldı; otomatik kilitleme yapılmayacak.</p>
      <small>Kilitledikten sonra bu şampiyon için kayıtlı ayarların varsa uygulanır.</small></div>
      {!health && <p role="status">Bağlantı doğrulanamıyor. League istemcisindeki seçimi kontrol et; son manuel seçim uyarısı korunuyor.</p>}
      {soundBlocked && !muted && <p className="selection-alert__sound" role="status">Ses çalınamadı. Uyarı ekranda kalacak; sesi tekrar deneyebilirsin.</p>}
      <div className="selection-alert__actions">
        <button className="button button--secondary" disabled={muted || stopping} onClick={() => { void sound() }}><Volume2 size={14} /><span>Uyarıyı dinle</span></button>
        <button className="button button--secondary" aria-pressed={muted} onClick={() => { audioEpoch.current++; current.current.muted = !muted; setMuted(!muted); if (!muted) stopSelectionSound() }}><VolumeX size={14} /><span>{muted ? 'Sesi aç' : 'Sesi kapat'}</span></button>
        <button className="button button--secondary" disabled={stopping} onClick={() => { audioEpoch.current++; current.current.stopping = true; stopSelectionSound(); onStop() }}>Otomasyonu durdur</button>
      </div>
    </div>
  </section>
}
