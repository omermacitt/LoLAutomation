import champions from '../assets/riot/champions.svg'
import runes from '../assets/riot/runes.svg'
import skins from '../assets/riot/skins.svg'
import './SectionIcon.css'

const icons = { champions, runes, skins }

export function SectionIcon({ section, size = 20 }: { section: keyof typeof icons; size?: number }) {
  const mask = `url("${icons[section]}") center / contain no-repeat`
  return <span className="section-icon" aria-hidden="true" style={{ width: size, height: size, flex: '0 0 auto', mask, WebkitMask: mask }} />
}
