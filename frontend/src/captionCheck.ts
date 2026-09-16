// What makes a caption hard to read, and what to say about it.
//
// The numbers come from subtitling practice rather than from taste: past about two and a half
// words a second a viewer stops reading and starts skipping, and a line that stands longer
// than seven seconds has been read three times over. The third check is this app's own: a word
// the church has already written down as a mishearing, still sitting in the text.
import type { Segment } from './api'

export const WORDS_PER_SECOND = 2.5
export const LONGEST = 7.0

export interface Trouble {
  kind: 'fast' | 'long' | 'misheard'
  says: string
}

/** The word in this line that the church's list has a correction for, if there is one. */
export function misheard(text: string, corrections: Record<string, string>): string | null {
  const said = text.toLowerCase()
  for (const wrong of Object.keys(corrections)) {
    if (!wrong.trim()) continue
    const pattern = new RegExp(`\\b${wrong.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i')
    if (pattern.test(said)) return wrong
  }
  return null
}

/** What is wrong with this line, in the order a reader would notice it. */
export function troubleWith(seg: Segment, corrections: Record<string, string> = {}): Trouble[] {
  const found: Trouble[] = []
  const words = seg.text.trim().split(/\s+/).filter(Boolean).length
  const span = seg.end - seg.start
  if (words && span > 0) {
    const pace = words / span
    if (pace > WORDS_PER_SECOND) {
      found.push({ kind: 'fast', says: `${pace.toFixed(1)} woorden per seconde, dat leest niemand` })
    }
  }
  if (span > LONGEST) {
    found.push({ kind: 'long', says: `${span.toFixed(0)} seconden in beeld, te lang om te blijven staan` })
  }
  const wrong = misheard(seg.text, corrections)
  if (wrong) {
    found.push({ kind: 'misheard', says: `"${wrong}" staat in de woordenlijst als ${corrections[wrong]}` })
  }
  return found
}
