import { useState } from 'react'
import type { ClipCandidate, Segment, Service } from '../api'
import { formatTime, parseTime } from '../subtitleLayout'

interface Props {
  service: Service
  video: React.RefObject<HTMLVideoElement | null>
  playing: string | null
  disabled: boolean
  onPreview: (candidate: ClipCandidate) => void
  onChange: (candidates: ClipCandidate[]) => void
}

/** The list of moments: the ones somebody cut by hand first, then what the search found. */
export default function ClipSuggestions({ service, video, playing, disabled, onPreview, onChange }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [showRest, setShowRest] = useState(false)
  const duration = service.sourceInfo?.duration ?? 1
  const segments = service.transcriptData?.segments ?? []

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
                + ` ${cand.shortlisted ? '' : 'aside'} ${own ? 'own' : ''}`}
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

              <div className="acts">
                <button className="small" onClick={() => onPreview(cand)}>
                  {playing === cand.id ? '■ Stop' : '▶ Beluister'}
                </button>
                <button className="small" onClick={() => setExpanded(open ? null : cand.id)}>
                  {open ? 'Verberg tekst en tijden' : 'Tekst en tijden'}
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
                  <Boundary
                    label="Begin"
                    value={cand.start}
                    min={0}
                    max={cand.end - 1}
                    disabled={disabled}
                    onChange={(t) => update(cand.id, { start: t })}
                    onJump={() => video.current && (video.current.currentTime = cand.start)}
                  />
                  <Boundary
                    label="Einde"
                    value={cand.end}
                    min={cand.start + 1}
                    max={duration}
                    disabled={disabled}
                    onChange={(t) => update(cand.id, { end: t })}
                    onJump={() => video.current && (video.current.currentTime = Math.max(cand.start, cand.end - 3))}
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

interface BoundaryProps {
  label: string
  value: number
  min: number
  max: number
  disabled: boolean
  onChange: (t: number) => void
  onJump: () => void
}

function Boundary({ label, value, min, max, disabled, onChange, onJump }: BoundaryProps) {
  const [text, setText] = useState(formatTime(value))
  const [lastValue, setLastValue] = useState(value)
  if (value !== lastValue) {
    setLastValue(value)
    setText(formatTime(value))
  }
  const clamp = (t: number) => Math.round(Math.min(max, Math.max(min, t)) * 10) / 10
  const commit = () => {
    const parsed = parseTime(text)
    if (parsed === null) setText(formatTime(value))
    else onChange(clamp(parsed))
  }
  return (
    <div className="row">
      <span>{label}</span>
      <button className="small" disabled={disabled} onClick={() => onChange(clamp(value - 5))}>−5</button>
      <button className="small" disabled={disabled} onClick={() => onChange(clamp(value - 1))}>−1</button>
      <input value={text} disabled={disabled} onChange={(e) => setText(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()} title="minuten:seconden" />
      <button className="small" disabled={disabled} onClick={() => onChange(clamp(value + 1))}>+1</button>
      <button className="small" disabled={disabled} onClick={() => onChange(clamp(value + 5))}>+5</button>
      <button className="small bare" onClick={onJump} title="Spring hierheen in de speler">▶</button>
    </div>
  )
}
