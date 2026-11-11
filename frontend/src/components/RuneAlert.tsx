import { useRef } from 'react'
import type { Health } from '../api/contracts'
import { roles } from '../features/champions/selection'

export function RuneAlert({ health }: { health?: Health }) {
  const previous = useRef<Health['rune_notice']>(null)
  if (health) previous.current = health.running ? health.rune_notice ?? null : null
  const notice = previous.current
  if (!notice) return null
  const role = roles.find((item) => item.key === notice.role)?.name ?? 'Rol bilgisi yok'
  return <aside className="error-banner rune-notice" role="alert" aria-label="Rün uygulama bildirimi">
    <strong>{notice.code === 'rune_fallback' ? 'Kayıtlı preset kullanılamadı; önerilen rünlere dönüldü.' : 'Rünler uygulanamadı; League istemcisindeki rünlerini kontrol et.'}</strong>
    <p>{role} · Şampiyon #{notice.champion_id}. {notice.code === 'rune_fallback' ? 'Önerilen sayfa veri paketinden gelir.' : 'Kullanılabilir sayfa bulunamadı. Mevcut istemci rünleri korunuyor.'}</p>
    {!health && <p>Bağlantı doğrulanamıyor; son rün uyarısı korunuyor.</p>}
  </aside>
}
