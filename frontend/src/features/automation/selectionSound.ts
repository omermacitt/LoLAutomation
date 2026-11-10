let context: AudioContext | undefined
let playing: OscillatorNode | undefined

export function stopSelectionSound() {
  try { playing?.stop() } catch { /* Already stopped. */ }
  playing = undefined
}

export async function prepareSelectionSound(): Promise<boolean> {
  try {
    if (!window.AudioContext) return false
    context ??= new AudioContext()
    if (context.state === 'running') return true
    return await Promise.race([
      context.resume().then(() => context?.state === 'running'),
      new Promise<false>((resolve) => setTimeout(() => resolve(false), 600)),
    ])
  } catch { return false }
}

export async function playSelectionSound(canPlay: () => boolean = () => true): Promise<boolean> {
  if (!await prepareSelectionSound() || !context || !canPlay()) return false
  try {
    stopSelectionSound()
    const oscillator = context.createOscillator()
    playing = oscillator
    const gain = context.createGain()
    const now = context.currentTime
    oscillator.frequency.setValueAtTime(880, now)
    oscillator.frequency.setValueAtTime(660, now + 0.18)
    gain.gain.setValueAtTime(0, now)
    gain.gain.linearRampToValueAtTime(0.12, now + 0.02)
    gain.gain.linearRampToValueAtTime(0, now + 0.42)
    oscillator.connect(gain)
    gain.connect(context.destination)
    oscillator.start(now)
    oscillator.stop(now + 0.45)
    oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); if (playing === oscillator) playing = undefined }
    return true
  } catch { return false }
}
