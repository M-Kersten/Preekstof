/**
 * Where a hook made of words first..last is cut. Mirrors hooks.edges in backend/hooks.py:
 * a little room in front of the first word and behind the last, never into a neighbour.
 * tests/mirror_cases.py writes the Python answers that test/mirror.ts diffs against.
 */
import type { Spoken } from './api'

export const BEFORE = 0.12
export const AFTER = 0.3
export const GAP = 0.03
/** The same limits the server checks a proposal against (hooks.py). */
export const SHORTEST = 1.5
export const LONGEST = 5
export const EARLIEST = 6
/** What the server takes from somebody choosing by hand (hooks.by_hand). */
export const LONGEST_BY_HAND = 10

const round2 = (value: number) => Math.round(value * 100) / 100

export function hookEdges(words: Spoken[], first: number, last: number, length: number): { start: number; end: number } {
  let start = words[first].start - BEFORE
  if (first > 0) start = Math.max(start, words[first - 1].end + GAP)
  let end = words[last].end + AFTER
  if (last + 1 < words.length) end = Math.min(end, words[last + 1].start - GAP)
  start = Math.max(0, Math.min(start, words[first].start))
  end = Math.min(length, Math.max(end, words[last].end))
  return { start: round2(start), end: round2(end) }
}

/**
 * Words a sentence opens with when it finishes something the listener already heard. A copy
 * of COLD_WORDS and COLD_PHRASES in backend/discovery.py, which tests/test_hooks.py compares.
 * Only advice here: somebody choosing by hand may know better.
 */
export const COLD_WORDS = new Set(["bovendien", "daardoor", "daarin", "daarmee", "daarna", "daarnaast", "daarom", "daarover", "daaruit", "daarvan", "dan", "dat", "deze", "die", "dit", "dus", "haar", "hem", "hen", "hierdoor", "hierin", "hiermee", "hiervan", "hij", "hun", "immers", "namelijk", "ook", "toch", "trouwens", "vandaar", "vervolgens", "want", "ze", "zij", "zo"])
export const COLD_PHRASES = ["zoals ik", "zoals we", "zoals gezegd", "zoals net", "zoals je net", "daarnet", "zonet", "net al", "wat ik net", "dat wil zeggen", "met andere woorden"]

/** The words this text leans back with, or '' when it stands on its own (discovery.cold_open). */
export function leansBack(text: string): string {
  const said = text.trim()
  const head = said.toLowerCase()
  if (!head) return ''
  const phrase = COLD_PHRASES.find((p) => head.startsWith(p))
  if (phrase) return said.slice(0, phrase.length)
  const found = head.match(/^[a-zà-ÿ']+/)
  if (!found) return ''
  if (found[0] === 'en') {
    const next = head.slice(found[0].length).match(/[a-zà-ÿ']+/)
    return next && COLD_WORDS.has(next[0]) ? said.split(/\s+/).slice(0, 2).join(' ') : ''
  }
  return COLD_WORDS.has(found[0]) ? said.split(/\s+/)[0] : ''
}
