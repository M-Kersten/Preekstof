// Where a fragment begins and ends, word by word. The clip is cut from the recording at
// exactly these seconds, so a boundary that lands inside a word cuts that word in half.
import type { Segment, Spoken } from './api'
import { wordTimes } from './subtitleLayout.ts'

export type Edge = 'start' | 'end'

/** Left after the last word, so its tail is not clipped off. */
export const AFTER_WORD = 0.25
/** Taken before the first word, so the clip does not open on half a breath. */
export const BEFORE_WORD = 0.15
const CLEAR = 0.05 // never closer than this to the word on the other side of the cut
const PAUSE = 0.7 // a silence this long ends a sentence even without a full stop

const round2 = (t: number) => Math.round(t * 100) / 100

/** Every word of the service in order, with when it is said. */
export function allWords(segments: Segment[]): Spoken[] {
  return segments.flatMap((s) => wordTimes(s))
}

/** The clip ends right after word `i`: a breath after it, but never into the next one. */
export function endAfter(words: Spoken[], i: number): number {
  const next = words[i + 1]
  const room = next ? next.start - CLEAR : Number.POSITIVE_INFINITY
  return round2(Math.max(words[i].end + CLEAR, Math.min(words[i].end + AFTER_WORD, room)))
}

/** The clip starts right before word `i`, without taking the end of the one before. */
export function startBefore(words: Spoken[], i: number): number {
  const before = words[i - 1]
  const room = before ? before.end + CLEAR : 0
  return round2(Math.max(0, Math.min(words[i].start, Math.max(words[i].start - BEFORE_WORD, room))))
}

/** Where a boundary would go if it were put at word `i`. */
export const placeAt = (words: Spoken[], edge: Edge, i: number): number =>
  edge === 'end' ? endAfter(words, i) : startBefore(words, i)

/** Does a sentence end with word `i`? A full stop says so, and so does a long silence. */
export function endsSentence(words: Spoken[], i: number): boolean {
  if (i >= words.length - 1) return true
  return /[.?!…]["'”’)]*$/.test(words[i].word) || words[i + 1].start - words[i].end >= PAUSE
}

/** The word a boundary belongs to: the last one inside before an end, the first one inside after a start. */
export function wordAt(words: Spoken[], edge: Edge, at: number): number {
  const middle = (w: Spoken) => (w.start + w.end) / 2
  if (edge === 'end') {
    let last = -1
    words.forEach((w, i) => middle(w) < at && (last = i))
    return last
  }
  const first = words.findIndex((w) => middle(w) >= at)
  return first === -1 ? words.length : first
}

/** Is the boundary cutting through a word right now? */
export function splits(words: Spoken[], at: number): Spoken | null {
  return words.find((w) => w.start + 0.04 < at && at < w.end - 0.04) ?? null
}

/**
 * The next place a sentence ends (for an end) or begins (for a start), in either direction.
 * Null when there is none that way.
 */
export function nextSentence(words: Spoken[], edge: Edge, at: number, way: 1 | -1): number | null {
  const places: number[] = []
  words.forEach((_, i) => {
    if (edge === 'end' && endsSentence(words, i)) places.push(endAfter(words, i))
    if (edge === 'start' && (i === 0 || endsSentence(words, i - 1))) places.push(startBefore(words, i))
  })
  const ahead = way === 1 ? places.filter((t) => t > at + CLEAR) : places.filter((t) => t < at - CLEAR).reverse()
  return ahead.length ? ahead[0] : null
}

/** The words on either side of a boundary, for showing where the cut falls. */
export function around(words: Spoken[], edge: Edge, at: number, inside: number, outside: number) {
  const word = wordAt(words, edge, at)
  // Inside the clip is before an end and after a start; `cut` is the first word past the line.
  const cut = edge === 'end' ? word + 1 : word
  const from = Math.max(0, cut - (edge === 'end' ? inside : outside))
  const to = Math.min(words.length, cut + (edge === 'end' ? outside : inside))
  return { from, cut, to }
}
