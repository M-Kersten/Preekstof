/** Putting the begin and end of a fragment between words instead of through them. */
import { allWords, around, endAfter, endsSentence, nextSentence, placeAt, splits, startBefore, wordAt } from '../src/edges.ts'
import type { Segment } from '../src/api.ts'

const problems: string[] = []
let checked = 0

const is = (what: string, got: unknown, wanted: unknown) => {
  checked += 1
  const a = JSON.stringify(got)
  const b = JSON.stringify(wanted)
  if (a !== b) problems.push(`${what}\n  wanted: ${b}\n  got:    ${a}`)
}

const w = (word: string, start: number, end: number) => ({ word, start, end })
const service: Segment[] = [
  { start: 10, end: 13.2, text: 'Genade is geen beloning.',
    words: [w('Genade', 10, 10.6), w('is', 10.7, 10.9), w('geen', 11, 11.4), w('beloning.', 11.5, 12.2)] },
  { start: 12.4, end: 15, text: 'Het is een geschenk',
    words: [w('Het', 12.4, 12.6), w('is', 12.7, 12.8), w('een', 12.9, 13.1), w('geschenk', 13.2, 14)] },
  { start: 15.2, end: 17, text: 'en dat verandert alles.',
    words: [w('en', 15.2, 15.4), w('dat', 15.5, 15.7), w('verandert', 15.8, 16.4), w('alles.', 16.5, 17)] },
]
const words = allWords(service)

is('every word of the service, in order', words.length, 12)
is('an end leaves a breath after the word', endAfter(words, 11), 17.25)
is('... but never runs into the next word', endAfter(words, 3), 12.35)
is('a start takes a moment before the word', startBefore(words, 0), 9.85)
is('... but never the tail of the word before', startBefore(words, 4), 12.25)
is('a full stop ends a sentence', endsSentence(words, 3), true)
is('a word in the middle does not', endsSentence(words, 5), false)
is('a long silence ends one too', endsSentence(words, 7), true)
is('the last word an end keeps', wordAt(words, 'end', 12.3), 3)
is('the first word a start keeps', wordAt(words, 'start', 12.3), 4)
is('placing an end at a word', placeAt(words, 'end', 7), endAfter(words, 7))
is('a cut through a word is noticed', splits(words, 13.6)?.word, 'geschenk')
is('a cut between words is fine', splits(words, 12.3), null)
is('the next sentence end', nextSentence(words, 'end', 12.35, 1), endAfter(words, 7))
is('the sentence end before', nextSentence(words, 'end', 14.25, -1), endAfter(words, 3))
is('nothing before the first', nextSentence(words, 'end', endAfter(words, 3), -1), null)
is('the next sentence start', nextSentence(words, 'start', 9.85, 1), startBefore(words, 4))
is('words shown around an end', around(words, 'end', 12.35, 2, 1), { from: 2, cut: 4, to: 5 })
is('words shown around a start', around(words, 'start', 12.25, 2, 1), { from: 3, cut: 4, to: 6 })

if (problems.length) {
  console.error(problems.join('\n\n'))
  process.exit(1)
}
console.log(`edges: ${checked} checks passed`)
