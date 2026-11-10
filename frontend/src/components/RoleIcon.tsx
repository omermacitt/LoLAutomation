import type { RoleKey } from '../features/champions/selection'

const paths: Record<RoleKey, string> = {
  TOP: 'M5 15V5h10M5 5l5 5M10 5h5v5M9 15h6V9',
  JUNGLE: 'M10 18C4 15 4 10 4 4l5 7M10 18c6-3 6-8 6-14l-5 7M10 18V8l-2-5',
  MIDDLE: 'M4 14 14 4h3v3L7 17H4v-3ZM4 8V4h4M12 17h5v-5',
  BOTTOM: 'M15 5v10H5M15 15l-5-5M10 15H5v-5M11 5H5v6',
  UTILITY: 'm3 6 7 4 7-4-2 6-5 3-5-3-2-6ZM10 10v8M7 18h6',
}

export function RoleIcon({ role, size = 22 }: { role: RoleKey; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 20 22" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[role]} /></svg>
}
