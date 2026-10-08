import { Fragment, useMemo, useState } from 'react'
import type { ClipCandidate, Segment, Service, Spoken } from '../api'
import { type Edge, allWords, around, nextSentence, placeAt, splits } from '../edges'
import { alreadyMade, madeOf } from '../versions'
import { formatTime, parseTime } from '../subtitleLayout'

interface Props {
  service: Service
  playing: string | null
  disabled: boolean
  onPreview: (candidate: ClipCandidate) => void
  /** Play the seconds around a boundary, the way the clip will: stopping on the cut, or starting on it. */
  onListen: (candidate: ClipCandidate, edge: Edge, at: number) => void
  onChange: (candidates: ClipCandidate[]) => void
  onOpenClip: (projectId: string) => void
}

/** The list of moments: the ones somebody cut by hand first, then what the search found. */
export default function ClipSuggestions({ service, playing, disabled, onPreview, onListen, onChange, onOpenClip }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [showRest, setShowRest] = useState(false)
  const duration = service.sourceInfo?.duration ?? 1
  const segments = useMemo(() => service.transcriptData?.segments ?? [], [service.transcriptData])
  const words = useMemo(() => allWords(segments), [segments])

  const update = (id: string, patch: Partial<ClipCandidate>) =>
    onChange(service.candidates.map((c) => (c.id === id ? { ...c, ...patch } : c)))
  const remove = (id: string) => onChange(service.candidates.filter((c) => c.id !== id))

  const rest = service.candidates.filter((c) => !c.shortlisted)

  if (service.candidates.length === 0) {
    return (
      <p className="say">
        Er is nog geen enkel fragment. Zoek de beste momenten, of knip er zelf een uit de tekst
        hiernaast.
      </p>
    )
  }

  return (
    <div>
      {service.candidates.map((cand, index) => {
        const excerpt = segments.filter((s) => s.end > cand.start && s.start < cand.end)
        const open = expanded === cand.id
        const own = cand.source === 'self'
        const opensRest = rest.length > 0 && cand.id === rest[0].id
        const versions = madeOf(service.clips, cand)
        const same = versions.length > 0 && alreadyMade(service.clips, cand)
        return (
          <div key={cand.id}>
            {opensRest && (
              <div className="also">
                <button className="bare" onClick={() => setShowRest(!showRest)} aria-expanded={showRest}>
                  {showRest ? '▾' : '▸'} Ook gevonden, niet gekozen ({rest.length})
                </button>
                <span className="meta">Deze momenten zijn wel voorgesteld, maar een ander moment was sterker.</span>
              </div>
            )}
            <article
              id={`f-${cand.id}`}
              hidden={!cand.shortlisted && !showRest}
              className={`suggestion ${cand.selected ? 'chosen' : ''} ${playing === cand.id ? 'playing' : ''}`
                + ` ${cand.shortlisted ? '' : 'aside'} ${own ? 'own' : ''} ${versions.length ? 'made' : ''}`}
            >
              <header>
                <span className="no">{String(index + 1).padStart(2, '0')}</span>
                <div className="head-main">
                  <h3>{cand.title}</h3>
                  <span className="meta tc">{formatTime(cand.start)} – {formatTime(cand.end)}</span>
                  <span className="meta"> · {Math.round(cand.end - cand.start)} sec</span>
                  {own && <span className="badge">zelf geknipt</span>}
                </div>
                <button
                  className={`pick ${cand.selected ? 'on' : ''}`}
                  aria-pressed={cand.selected}
                  disabled={disabled}
                  onClick={() => update(cand.id, { selected: !cand.selected })}
                >
                  {cand.selected ? '✓ Gekozen' : 'Kies dit'}
                </button>
              </header>

              {excerpt.length > 0 && (
                <blockquote className="quote">
                  {open ? excerpt.map((s) => s.text.trim()).join(' ') : shorten(excerpt, 190)}
                </blockquote>
              )}
              {cand.summary && <p>{cand.summary}</p>}
              {cand.verdict && <p className="verdict">{cand.verdict}</p>}
              {cand.reason && <p className="why">{cand.reason}</p>}

              {versions.length > 0 && (
                <div className="made-here">
                  <span>
                    ✓ Verwerkt{versions.length > 1 ? `, ${versions.length} versies` : ''}
                    {cand.selected && (
                      <span className="meta">
                        {' · '}
                        {same
                          ? 'zo is hij al gemaakt. Nog een keer verwerken geeft een kopie.'
                          : 'verwerken maakt een nieuwe versie met dit begin en einde. De vorige blijft staan.'}
                      </span>
                    )}
                  </span>
                  <button className="small" onClick={() => onOpenClip(versions[0].projectId)}>
                    {versions.length > 1 ? 'Nieuwste bewerken →' : 'Bewerken →'}
                  </button>
                </div>
              )}

              <div className="acts">
                <button className="small" onClick={() => onPreview(cand)}>
                  {playing === cand.id ? '■ Stop' : '▶ Beluister'}
                </button>
                <button className="small" onClick={() => setExpanded(open ? null : cand.id)} aria-expanded={open}>
                  {open ? 'Klaar met begin en einde' : 'Begin en einde bijstellen'}
                </button>
                {/* Only the hand-cut ones can go: a found one is the search's answer, and
                    hiding it would make "opnieuw zoeken" bring it straight back. */}
                {own && (
                  <button
                    className="small bare"
                    disabled={disabled}
                    onClick={() => remove(cand.id)}
                    title="Dit fragment weghalen"
                  >
                    Weghalen
                  </button>
                )}
              </div>

              {open && (
                <div className="trim">
                  <p className="hint">
                    Klik op het woord waar de clip moet beginnen of ophouden. Na elke verandering hoor je meteen hoe
                    het begint of eindigt.
                  </p>
                  <EdgeRow
                    edge="start"
                    value={cand.start}
                    min={0}
                    max={cand.end - 1}
                    words={words}
                    disabled={disabled}
                    onChange={(t) => update(cand.id, { start: t })}
                    onListen={(t) => onListen(cand, 'start', t)}
                  />
                  <EdgeRow
                    edge="end"
                    value={cand.end}
                    min={cand.start + 1}
                    max={duration}
                    words={words}
                    disabled={disabled}
                    onChange={(t) => update(cand.id, { end: t })}
                    onListen={(t) => onListen(cand, 'end', t)}
                  />
                  {cand.alternateBoundaries.length > 0 && (
                    <div className="row">
                      <span>Anders</span>
                      {cand.alternateBoundaries.map((alt, i) => (
                        <button key={i} className="small" disabled={disabled} onClick={() => update(cand.id, { start: alt.start, end: alt.end })}>
                          {formatTime(alt.start)} – {formatTime(alt.end)}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="lines">
                    {excerpt.map((s, i) => (
                      <div key={i}><span className="tc">{formatTime(s.start)}</span> {s.text}</div>
                    ))}
                  </div>
                </div>
              )}
            </article>
          </div>
        )
      })}
    </div>
  )
}

function shorten(segments: Segment[], max: number): string {
  const text = segments.map((s) => s.text.trim()).join(' ')
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text
}

interface EdgeProps {
  edge: Edge
  value: number
  min: number
  max: number
  words: Spoken[]
  disabled: boolean
  onChange: (t: number) => void
  onListen: (t: number) => void
}

const SHOWN_INSIDE = 9 // words shown on the clip's side of the cut
const SHOWN_OUTSIDE = 5 // ... and on the side that is left out

/**
 * One boundary of a fragment: the words around the cut, and ways to move it.
 *
 * A boundary is set by ear, so every change plays the seconds around it straight away, the
 * way the clip will: up to the cut for an end, from the cut for a start.
 */
function EdgeRow({ edge, value, min, max, words, disabled, onChange, onListen }: EdgeProps) {
  const [text, setText] = useState(formatTime(value))
  const [lastValue, setLastValue] = useState(value)
  if (value !== lastValue) {
    setLastValue(value)
    setText(formatTime(value))
  }
  const clamp = (t: number) => Math.round(Math.min(max, Math.max(min, t)) * 100) / 100
  const set = (t: number) => {
    const next = clamp(t)
    onChange(next)
    onListen(next)
  }
  const commit = () => {
    const parsed = parseTime(text)
    if (parsed === null) setText(formatTime(value))
    else if (clamp(parsed) !== value) set(parsed)
  }
  const ending = edge === 'end'
  const { from, cut, to } = around(words, edge, value, SHOWN_INSIDE, SHOWN_OUTSIDE)
  const split = splits(words, value)
  const back = nextSentence(words, edge, value, -1)
  const ahead = nextSentence(words, edge, value, 1)
  const mark = <span className="cutmark" aria-hidden="true" />

  return (
    <div className="edge">
      <div className="row">
        <span>{ending ? 'Einde' : 'Begin'}</span>
        <button className="small" disabled={disabled} onClick={() => set(value - 1)} title="Een seconde eerder">−1 s</button>
        <input value={text} disabled={disabled} onChange={(e) => setText(e.target.value)} onBlur={commit}
               onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()} title="minuten:seconden"
               aria-label={ending ? 'Einde van het fragment' : 'Begin van het fragment'} />
        <button className="small" disabled={disabled} onClick={() => set(value + 1)} title="Een seconde later">+1 s</button>
        <span className="gap" />
        <button className="small" disabled={disabled || back === null} onClick={() => back !== null && set(back)}
                title={ending ? 'Laat de clip eindigen waar de zin ervoor ophoudt' : 'Laat de clip beginnen bij de zin ervoor'}>
          ‹ zin
        </button>
        <button className="small" disabled={disabled || ahead === null} onClick={() => ahead !== null && set(ahead)}
                title={ending ? 'Laat de clip eindigen waar de volgende zin ophoudt' : 'Laat de clip beginnen bij de volgende zin'}>
          zin ›
        </button>
        <button className="small listen" onClick={() => onListen(value)}>
          ▶ {ending ? 'Hoor het einde' : 'Hoor het begin'}
        </button>
      </div>
      {words.length > 0 && (
        <p className={`cutline ${ending ? 'ends' : 'starts'}`}>
          {from > 0 && <span className="more">… </span>}
          {words.slice(from, to).map((w, k) => {
            const i = from + k
            const inside = ending ? i < cut : i >= cut
            return (
              <Fragment key={i}>
                {i === cut && mark}
                <button type="button" className={`word ${inside ? '' : 'out'}`} disabled={disabled}
                        onClick={() => set(placeAt(words, edge, i))}
                        title={ending ? 'Laat de clip na dit woord ophouden' : 'Laat de clip met dit woord beginnen'}>
                  {w.word}
                </button>{' '}
              </Fragment>
            )
          })}
          {cut >= to && mark}
          {to < words.length && <span className="more">…</span>}
        </p>
      )}
      {split && <p className="warn">De knip valt nu midden in “{split.word}”. Klik op een woord om er netjes omheen te knippen.</p>}
    </div>
  )
}
