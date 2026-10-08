/** The clips of a service, one entry per fragment with its versions under it. */
import { alreadyMade, byFragment, madeOf } from '../src/versions.ts'
import type { ClipCandidate, ProcessedClip } from '../src/api.ts'

const problems: string[] = []
let checked = 0

const is = (what: string, got: unknown, wanted: unknown) => {
  checked += 1
  const a = JSON.stringify(got)
  const b = JSON.stringify(wanted)
  if (a !== b) problems.push(`${what}\n  wanted: ${b}\n  got:    ${a}`)
}

const clip = (projectId: string, candidateId: string, title: string, start: number, end: number): ProcessedClip =>
  ({ candidateId, projectId, title, start, end, createdAt: '2026-10-08T10:00:00' })
const fragment = (id: string, title: string, start: number, end: number) =>
  ({ id, title, start, end }) as ClipCandidate

const fragments = [fragment('late', 'Gods gave', 900, 940), fragment('early', 'Genade', 300, 345)]
const clips = [
  clip('p1', 'late', 'Gods gave', 900, 940),
  clip('p2', 'early', 'Genade', 300, 340),
  clip('p3', 'early', 'Genade', 300, 345),
  clip('p4', 'early', 'Genade', 300, 345),
  clip('p5', 'gone', 'Weggegooid', 1200, 1230),
]
const made = byFragment(clips, fragments)

is('one entry per fragment', made.map((m) => m.key), ['early', 'late', 'gone'])
is('versions newest first', made[0].versions.map((v) => v.projectId), ['p4', 'p3', 'p2'])
is('numbered in the order they were made', made[0].versions.map((v) => v.number), [3, 2, 1])
is('the newest is marked', made[0].versions.map((v) => v.latest), [true, false, false])
is('a second make of the same cut is a copy', made[0].versions.map((v) => v.copy), [true, true, false])
is('a fragment that is gone keeps its title', made[2].title, 'Weggegooid')
is('the versions of one fragment', madeOf(clips, fragments[1]).map((v) => v.projectId), ['p4', 'p3', 'p2'])
is('nothing made yet', madeOf(clips, fragment('new', 'Nieuw', 10, 20)), [])
is('cut exactly like this before', alreadyMade(clips, fragments[1]), true)
is('cut differently now', alreadyMade(clips, fragment('early', 'Genade', 301, 345)), false)

if (problems.length) {
  console.error(problems.join('\n\n'))
  process.exit(1)
}
console.log(`versions: ${checked} checks passed`)
