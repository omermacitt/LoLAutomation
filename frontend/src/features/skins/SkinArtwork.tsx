import { useState } from 'react'
import { ImageOff } from 'lucide-react'
import { skinArtworkUrl } from '../../api/client'
import { ChampionArtwork } from '../../components/ChampionArtwork'

export function SkinArtwork({ championId, skinId, championName, retryKey, eager = false }: {
  championId: number; skinId: number; championName: string; retryKey: number; eager?: boolean
}) {
  const [failed, setFailed] = useState<string>()
  const key = `${championId}:${skinId}:${retryKey}`
  return <span className="skin-artwork" aria-hidden="true">
    {failed === key ? <span className="skin-artwork__fallback">
      <ChampionArtwork id={championId} name={championName} retryKey={retryKey} />
      <span><ImageOff size={16} />Görsel yüklenemedi</span>
    </span> : <img key={key} src={skinArtworkUrl(championId, skinId)} alt="" loading={eager ? 'eager' : 'lazy'}
      decoding="async" onError={() => setFailed(key)} />}
  </span>
}
