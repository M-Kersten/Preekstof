// The clips made from a service, put back together per fragment. Processing a fragment again
// makes a second clip next to the first, under the same title; listed loose they look like
// the same clip twice.
import type { ClipCandidate, ProcessedClip } from './api'

export interface Version extends ProcessedClip {
  number: number // 1 for the first time the fragment was made, counting up
  latest: boolean
  /** Another version has the very same begin and end: a copy rather than a new cut. */
  copy: boolean
}

export interface Made {
  key: string
  title: string
  start: number
  versions: Version[] // newest first
}

const SAME = 0.05 // seconds: begin and end this close count as the same cut

/** One entry per fragment, in the order the fragments come in the service. */
export function byFragment(clips: ProcessedClip[], candidates: ClipCandidate[]): Made[] {
  const groups = new Map<string, ProcessedClip[]>()
  for (const clip of clips) {
    // Older services, or a fragment that was thrown away since: its title still holds it together.
    const key = clip.candidateId || `title:${clip.title}`
    groups.set(key, [...(groups.get(key) ?? []), clip])
  }
  const made: Made[] = []
  for (const [key, list] of groups) {
    const versions = list.map((clip, i) => ({
      ...clip,
      number: i + 1,
      latest: i === list.length - 1,
      copy: list.some((other) => other !== clip && Math.abs(other.start - clip.start) < SAME
        && Math.abs(other.end - clip.end) < SAME),
    }))
    const fragment = candidates.find((c) => c.id === key)
    made.push({
      key,
      title: fragment?.title ?? list[list.length - 1].title,
      start: fragment?.start ?? list[0].start,
      versions: versions.reverse(),
    })
  }
  return made.sort((a, b) => a.start - b.start)
}

/** The versions already made of one fragment, newest first. */
export function madeOf(clips: ProcessedClip[], candidate: ClipCandidate): Version[] {
  return byFragment(clips.filter((c) => c.candidateId === candidate.id), [candidate])[0]?.versions ?? []
}

/** Is a fragment, as it is cut now, already made exactly like this? */
export function alreadyMade(clips: ProcessedClip[], candidate: ClipCandidate): boolean {
  return clips.some((c) => c.candidateId === candidate.id && Math.abs(c.start - candidate.start) < SAME
    && Math.abs(c.end - candidate.end) < SAME)
}
