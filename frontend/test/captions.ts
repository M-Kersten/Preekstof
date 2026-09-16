/** The caption checks, on the lines they are meant to catch. */
import { troubleWith, misheard } from '../src/captionCheck.ts'
import type { Segment } from '../src/api.ts'

const problems: string[] = []
let checked = 0

const seg = (text: string, start: number, end: number): Segment => ({ start, end, text })

const is = (what: string, got: unknown, wanted: unknown) => {
  checked += 1
  const a = JSON.stringify(got)
  const b = JSON.stringify(wanted)
  if (a !== b) problems.push(`${what}\n  wanted: ${b}\n  got:    ${a}`)
}

const kinds = (s: Segment, c: Record<string, string> = {}) => troubleWith(s, c).map((t) => t.kind)

// A line at a readable pace, in and out in good time.
is('calm line', kinds(seg('God is op zoek naar jou', 0, 3)), [])
// Six words in one second is a blur.
is('too fast', kinds(seg('God is op zoek naar jou', 0, 1)), ['fast'])
// Eight seconds on screen for four words: the viewer read it long ago.
is('too long', kinds(seg('God is op zoek', 0, 8)), ['long'])
// Both at once, in the order a reader notices them.
is('fast and long', kinds(seg('God is op zoek naar jou en hij vindt je ook waar je ook bent '
                             + 'en dat blijft zo of je het nu ziet of niet', 0, 7.5)),
   ['fast', 'long'])
// A word the church already wrote down as a mishearing.
is('known mishearing', kinds(seg('We zingen Lee 302', 0, 3), { lee: 'Lied' }), ['misheard'])
is('mishearing is caught whatever the case', misheard('Zingt LEE 302', { lee: 'Lied' }), 'lee')
is('a word inside another word is not a mishearing', misheard('Ik lees het', { lee: 'Lied' }), null)
is('nothing in the list, nothing to say', misheard('Zingt Lee 302', {}), null)
is('an empty line has no pace', kinds(seg('   ', 0, 3)), [])
is('a line of no length is not infinitely fast', kinds(seg('God', 2, 2)), [])

// The reason is worth reading, not just the fact.
const said = troubleWith(seg('God is op zoek naar jou', 0, 1))[0].says
if (!said.includes('woorden per seconde')) problems.push(`the reason does not say why: ${said}`)
checked += 1

if (problems.length) {
  console.error(`${problems.length} of ${checked} caption checks are wrong:\n`)
  console.error(problems.join('\n\n'))
  process.exit(1)
}
console.log(`${checked} caption checks agree`)
