/** Searching the transcript, and what a selection of lines comes to. */
import { hits, lengthTrouble, lineAt, pieces, plain, spanOf, titleFrom } from '../src/transcriptSearch.ts'
import type { Segment } from '../src/api.ts'

const problems: string[] = []
let checked = 0

const is = (what: string, got: unknown, wanted: unknown) => {
  checked += 1
  const a = JSON.stringify(got)
  const b = JSON.stringify(wanted)
  if (a !== b) problems.push(`${what}\n  wanted: ${b}\n  got:    ${a}`)
}

const seg = (text: string, start: number, end: number): Segment => ({ start, end, text })

const service: Segment[] = [
  seg('Goedemorgen allemaal, hartelijk welkom.', 0, 5),
  seg('We lezen vandaag uit Mattheüs elf.', 10, 16),
  seg('Kom naar mij, jullie die vermoeid zijn.', 20, 27),
  seg('Jezus zegt dat niet tegen de sterken.', 30, 36),
]

// --- finding something -----------------------------------------------------------

is('a word that is there', hits(service, 'vermoeid'), [2])
is('capitals do not matter', hits(service, 'JEZUS'), [3])
is('accents do not matter either', hits(service, 'mattheus'), [1])
is('nothing typed is no hits', hits(service, '   '), [])
is('a word that is not there', hits(service, 'olifant'), [])
is('a word in more than one line', hits(service, 'e'), [0, 1, 2, 3])
is('accents survive being folded', plain('Mattheüs'), 'mattheus')

// --- marking it in the line -------------------------------------------------------

is('the match keeps its own spelling', pieces('Uit Mattheüs elf', 'mattheus'),
   [{ text: 'Uit ', hit: false }, { text: 'Mattheüs', hit: true }, { text: ' elf', hit: false }])
is('a line with no match is one piece', pieces('Uit Mattheüs elf', 'olifant'),
   [{ text: 'Uit Mattheüs elf', hit: false }])
is('nothing typed leaves the line alone', pieces('Uit Mattheüs elf', ''),
   [{ text: 'Uit Mattheüs elf', hit: false }])
is('two matches in one line', pieces('ja en ja', 'ja'),
   [{ text: 'ja', hit: true }, { text: ' en ', hit: false }, { text: 'ja', hit: true }])
is('a match at the very end', pieces('zeg ja', 'ja'),
   [{ text: 'zeg ', hit: false }, { text: 'ja', hit: true }])

// --- what a selection covers -------------------------------------------------------

is('one line', spanOf(service, 2, 2), { start: 20, end: 27 })
is('a run of lines', spanOf(service, 1, 3), { start: 10, end: 36 })
is('clicked from the bottom up', spanOf(service, 3, 1), { start: 10, end: 36 })
is('a line that is not there', spanOf(service, 1, 9), null)

// --- the line being spoken ----------------------------------------------------------

is('during a line', lineAt(service, 22), 2)
is('exactly on the start', lineAt(service, 20), 2)
is('in the silence between two', lineAt(service, 8), -1)
is('after the last word', lineAt(service, 999), -1)

// --- what it is called ---------------------------------------------------------------

is('the opening sentence, without its full stop', titleFrom(service, 2, 3),
   'Kom naar mij, jullie die vermoeid zijn')
is('picked from the bottom up, still the first line', titleFrom(service, 3, 2),
   'Kom naar mij, jullie die vermoeid zijn')
const long = [seg('Dit is een hele lange zin die veel verder doorloopt dan zestig tekens lang is.', 0, 9)]
is('a long sentence is cut at a word', titleFrom(long, 0, 0),
   'Dit is een hele lange zin die veel verder doorloopt dan…')

// --- saying when it will not work as a clip ---------------------------------------------

is('a good length says nothing', lengthTrouble({ start: 0, end: 60 }), null)
if (!(lengthTrouble({ start: 0, end: 12 }) ?? '').includes('12 seconden')) {
  problems.push('a short selection does not say how short it is')
}
checked += 1
if (!(lengthTrouble({ start: 0, end: 600 }) ?? '').includes('minuten')) {
  problems.push('a long selection does not say it is too long')
}
checked += 1

if (problems.length) {
  console.error(`${problems.length} of ${checked} transcript checks are wrong:\n`)
  console.error(problems.join('\n\n'))
  process.exit(1)
}
console.log(`${checked} transcript checks agree`)
