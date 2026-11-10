import { useState } from 'react'
import type { CSSProperties } from 'react'
import { championPortraitUrl } from '../api/client'
import { initials } from '../features/champions/selection'

export function ChampionArtwork({ id, name, small = false, retryKey = 0 }: { id: number; name: string; small?: boolean; retryKey?: number }) {
  const hue = (id * 37 + 170) % 360
  const source = championPortraitUrl(id)
  const [loadedId, setLoadedId] = useState<number>()
  const [failure, setFailure] = useState<{ id: number; retry: number }>()
  const failed = failure?.id === id && failure.retry === retryKey
  return <span className={`champion-art ${small ? 'champion-art--small' : ''} ${loadedId === id ? 'champion-art--loaded' : ''}`} style={{ '--champion-hue': hue } as CSSProperties} aria-hidden="true">
    <span className="champion-art__diamond" />
    <span className="champion-art__initials">{initials(name)}</span>
    {!small && <span className="champion-art__number">{String(id).padStart(3, '0')}</span>}
    {source && !failed && <img key={id} className="champion-art__portrait" src={source} alt="" width={128} height={128} loading={small ? 'eager' : 'lazy'} decoding="async" draggable={false}
      onLoad={() => setLoadedId(id)} onError={() => { setLoadedId(undefined); setFailure({ id, retry: retryKey }) }} />}
  </span>
}
