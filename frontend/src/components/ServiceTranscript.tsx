import { useEffect, useMemo, useRef, useState } from 'react'
import type { ClipCandidate, Segment, Service } from '../api'
import { formatTime } from '../subtitleLayout'
import {
  hits as searchHits, lengthTrouble, lineAt, pieces, spanOf, titleFrom,
} from '../transcriptSearch'

interface Props {
  service: Service
  /** The player the whole page shares, so reading and listening are the same seat. */
  video: React.RefObject<HTMLVideoElement | null>
  time: number
  disabled: boolean
  onCut: (candidate: ClipCandidate) => void
}

/** How long a part has to last before it is worth a button of its own. */
const WORTH_A_JUMP = 60

/**
 * Where each part of the service begins, as somewhere to jump to.
 *
 * A morning has three blocks of singing in it, so the label alone says nothing about which
 * one a button leads to. The time does.
 */
function partStarts(service: Service, segments: Segment[]): { label: string; when: string; line: number }[] {
  return service.shape
    .filter((block) => block.end - block.start >= WORTH_A_JUMP)
    .map((block) => ({
      label: block.label,
      when: `${Math.floor(block.start / 60)}:${String(Math.floor(block.start % 60)).padStart(2, '0')}`,
      line: segments.findIndex((s) => s.end > block.start),
    }))
    .filter((jump) => jump.line >= 0)
}

/**
 * The whole service as text, to read through while the search is still running.
 *
 * Someone who has to have a clip out by lunchtime should not be sitting in front of a
 * progress bar. The text is there the moment it is written out, so they can read, look
 * something up and cut a moment they already had in mind. What they cut lands in the same
 * list as what the search finds, so there is one place to choose from and one button at
 * the bottom.
 */
export default function ServiceTranscript({ service, video, time, disabled, onCut }: Props) {
  const segments = service.transcriptData?.segments ?? []
  const [query, setQuery] = useState('')
  const [at, setAt] = useState(0)  // which hit the ‹ › buttons are standing on
  const [from, setFrom] = useState<number | null>(null)
  const [to, setTo] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [named, setNamed] = useState(false)  // the title is the user's once they have typed
  const [follow, setFollow] = useState(true)
  const list = useRef<HTMLDivElement>(null)
  const rows = useRef<(HTMLButtonElement | null)[]>([])

  const hits = useMemo(() => searchHits(segments, query), [segments, query])
  const speaking = lineAt(segments, time)
  const span = from === null || to === null ? null : spanOf(segments, from, to)
  const trouble = span ? lengthTrouble(span) : null

  const show = (line: number) => rows.current[line]?.scrollIntoView({ behavior: 'smooth', block: 'center' })

  const step = (by: number) => {
    if (hits.length === 0) return
    const next = (at + by + hits.length) % hits.length
    setAt(next)
    show(hits[next])
  }

  // A new search starts at its first hit rather than wherever the last one left off.
  useEffect(() => {
    setAt(0)
    if (hits.length > 0) show(hits[0])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  // Follow the recording while it plays, and stop the moment the reader scrolls away:
  // being dragged back to the playhead while looking something up is worse than no help.
  useEffect(() => {
    if (!follow || speaking < 0) return
    rows.current[speaking]?.scrollIntoView({ block: 'nearest' })
  }, [follow, speaking])

  const pick = (line: number, extend: boolean) => {
    // A click that ends a drag over the text is someone copying, not someone choosing.
    if ((window.getSelection()?.toString() ?? '').length > 0) return
    if (extend && from !== null) setTo(line)
    else {
      setFrom(line)
      setTo(line)
    }
    const other = extend && from !== null ? from : line
    if (!named) setTitle(titleFrom(segments, other, line))
    const v = video.current
    if (v && !extend) v.currentTime = segments[line].start
  }

  const clear = () => {
    setFrom(null)
    setTo(null)
    setTitle('')
    setNamed(false)
  }

  const play = () => {
    const v = video.current
    if (!v || !span) return
    v.currentTime = span.start
    void v.play().catch(() => undefined)
  }

  const make = () => {
    if (!span) return
    onCut({
      id: '', start: Math.round(span.start * 10) / 10, end: Math.round(span.end * 10) / 10,
      title: (title.trim() || titleFrom(segments, from!, to!)).slice(0, 80),
      summary: '', reason: '', confidence: 1, selected: true, score: 0,
      alternateBoundaries: [], shortlisted: true, verdict: '', part: '', source: 'self',
    })
    clear()
  }

  if (segments.length === 0) {
    return <p className="say">De uitgeschreven tekst is er nog niet.</p>
  }

  const lo = from === null ? -1 : Math.min(from, to ?? from)
  const hi = from === null ? -1 : Math.max(from, to ?? from)
  const jumps = partStarts(service, segments)

  return (
    <div className="reading">
      <div className="find">
        <input
          type="search"
          value={query}
          placeholder="Zoek een woord of een zin uit de dienst"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && step(e.shiftKey ? -1 : 1)}
        />
        {query.trim() && (
          <span className="found">
            {hits.length === 0 ? 'niets gevonden' : `${at + 1} van ${hits.length}`}
            <button className="bare small" disabled={hits.length === 0} onClick={() => step(-1)} title="Vorige">‹</button>
            <button className="bare small" disabled={hits.length === 0} onClick={() => step(1)} title="Volgende">›</button>
          </span>
        )}
      </div>

      {jumps.length > 1 && (
        <div className="jumps">
          <span className="meta">Spring naar</span>
          {jumps.map((jump, i) => (
            <button key={i} className="small" onClick={() => show(jump.line)}>
              {jump.label} <span className="tc muted">{jump.when}</span>
            </button>
          ))}
        </div>
      )}

      <p className="hint">
        Klik op een zin om daar te luisteren. Klik met <kbd>Shift</kbd> op een tweede zin om
        alles ertussen te pakken, en maak daar een fragment van.
      </p>

      {/* Only a wheel, a drag or a key means the reader went looking somewhere else. The
          list scrolling itself back to the playhead must not count, or following the
          recording would switch itself off the first time it worked. */}
      <div
        className="lines read"
        ref={list}
        onWheel={() => follow && setFollow(false)}
        onTouchMove={() => follow && setFollow(false)}
        onKeyDown={(e) => follow && ['PageDown', 'PageUp', 'Home', 'End'].includes(e.key) && setFollow(false)}
      >
        {segments.map((s, i) => (
          <button
            key={i}
            ref={(el) => { rows.current[i] = el }}
            className={`line${i >= lo && i <= hi ? ' picked' : ''}${i === speaking ? ' saying' : ''}`
              + `${hits[at] === i ? ' hit' : ''}`}
            onClick={(e) => pick(i, e.shiftKey)}
          >
            <span className="tc">{formatTime(s.start)}</span>
            <span>
              {pieces(s.text.trim(), query).map((piece, n) =>
                piece.hit ? <mark key={n}>{piece.text}</mark> : <span key={n}>{piece.text}</span>)}
            </span>
          </button>
        ))}
      </div>

      {span && (
        <div className="cutting">
          <div className="row">
            <span className="tc">{formatTime(span.start)} – {formatTime(span.end)}</span>
            <span className="meta">{Math.round(span.end - span.start)} sec</span>
            <input
              value={title}
              placeholder="Naam van dit fragment"
              onChange={(e) => {
                setTitle(e.target.value)
                setNamed(true)
              }}
            />
            <button className="small" onClick={play}>▶ Beluister</button>
            <button className="primary" disabled={disabled} onClick={make}>Fragment maken</button>
            <button className="bare small" onClick={clear} title="Laat deze selectie los">✕</button>
          </div>
          {trouble && <p className="hint">{trouble}</p>}
        </div>
      )}

      {/* Nothing to go back to while nothing is playing. */}
      {!follow && speaking >= 0 && (
        <button className="bare small follow" onClick={() => setFollow(true)}>
          ↓ Weer met de opname meelezen
        </button>
      )}
    </div>
  )
}
