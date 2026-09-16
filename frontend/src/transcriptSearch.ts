/**
 * Finding your way through an hour of transcript, and cutting a piece out of it.
 *
 * Kept away from the component so the rules can be read and tested on their own: what
 * counts as a hit, what a selection of lines covers in seconds, and what to call the
 * fragment somebody just cut.
 */
import type { Segment } from './api'

/** Shorter than this and there is no room to introduce anything (backend: MIN_CLIP). */
export const SHORTEST = 25
/** Longer than this and it is not a reel any more (backend: MAX_CLIP). */
export const LONGEST = 180
/** What a fragment is called until somebody types something better. */
export const TITLE_CHARS = 60

/** Lower case and without accents, so "Jezus" finds "jezus" and "Mattheüs" finds "mattheus". */
export function plain(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

/** Which lines the search term appears in, in the order they are said. */
export function hits(segments: Segment[], query: string): number[] {
  const needle = plain(query.trim())
  if (!needle) return []
  const found: number[] = []
  segments.forEach((s, i) => {
    if (plain(s.text).includes(needle)) found.push(i)
  })
  return found
}

export interface Piece {
  text: string
  hit: boolean
}

/**
 * One line cut into the bits that match and the bits that do not, so the match can be
 * marked without losing the original spelling and accents.
 */
export function pieces(text: string, query: string): Piece[] {
  const needle = plain(query.trim())
  if (!needle) return [{ text, hit: false }]
  const flat = plain(text)
  const out: Piece[] = []
  let at = 0
  for (;;) {
    const found = flat.indexOf(needle, at)
    if (found < 0) break
    if (found > at) out.push({ text: text.slice(at, found), hit: false })
    out.push({ text: text.slice(found, found + needle.length), hit: true })
    at = found + needle.length
  }
  if (at < text.length) out.push({ text: text.slice(at), hit: false })
  return out.length ? out : [{ text, hit: false }]
}

export interface Span {
  start: number
  end: number
}

/** The seconds a run of lines covers, whichever end you clicked first. */
export function spanOf(segments: Segment[], a: number, b: number): Span | null {
  const lo = Math.min(a, b)
  const hi = Math.max(a, b)
  if (lo < 0 || hi >= segments.length) return null
  return { start: segments[lo].start, end: segments[hi].end }
}

/** The line being spoken at this moment, or -1 between two of them. */
export function lineAt(segments: Segment[], time: number): number {
  for (let i = 0; i < segments.length; i += 1) {
    if (time < segments[i].start) return -1
    if (time <= segments[i].end) return i
  }
  return -1
}

/**
 * What to call a fragment nobody has named yet: its opening words, which is what a
 * scrolling viewer would see first anyway. Cut at a word, and never mid-sentence-and-a-half.
 */
export function titleFrom(segments: Segment[], a: number, b: number): string {
  const lo = Math.min(a, b)
  const said = (segments[lo]?.text ?? '').trim()
  if (said.length <= TITLE_CHARS) return said.replace(/[.,;:]$/, '')
  return `${said.slice(0, TITLE_CHARS).replace(/\s+\S*$/, '')}…`
}

/** What is wrong with the length of this selection, if anything, in one line of Dutch. */
export function lengthTrouble(span: Span): string | null {
  const seconds = span.end - span.start
  if (seconds < SHORTEST) {
    return `Dit is ${Math.round(seconds)} seconden. Onder de ${SHORTEST} is er geen ruimte om iets uit te leggen; neem er een paar zinnen aanloop bij.`
  }
  if (seconds > LONGEST) {
    return `Dit is ${Math.round(seconds / 60)} minuten. Boven de ${LONGEST / 60} minuten kijkt niemand het af.`
  }
  return null
}
