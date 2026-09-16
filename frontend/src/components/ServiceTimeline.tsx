import type { ClipCandidate, Service } from '../api'
import { formatTime } from '../subtitleLayout'

interface Props {
  service: Service
  time: number
  playing: string | null
  onPick: (candidate: ClipCandidate) => void
}

/** Minutes:seconds, for the timeline scale. */
function clock(seconds: number): string {
  const m = Math.floor(seconds / 60)
  return `${m}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
}

/**
 * Where everything sits in the hour: the parts of the service behind, the fragments in
 * front, the playhead on top.
 *
 * It sits above both ways of working, because it answers the same question in both: am I
 * in the sermon yet, and have I already got something from around here.
 */
export default function ServiceTimeline({ service, time, playing, onPick }: Props) {
  const duration = service.sourceInfo?.duration ?? 1
  return (
    <div className="timeline">
      {service.shape.length > 0 && (
        <div className="shape" aria-hidden="true">
          {service.shape.map((block, i) => {
            const share = (block.end - block.start) / duration
            return (
              <span
                key={i}
                className={`part ${block.part}`}
                style={{ left: `${(block.start / duration) * 100}%`, width: `${share * 100}%` }}
                title={`${block.label} · ${clock(block.start)}–${clock(block.end)}`}
              >
                {/* Too narrow to read is worse than blank; the tooltip still says what it is. */}
                {share > 0.09 && <span>{block.label}</span>}
              </span>
            )
          })}
        </div>
      )}
      <div className="rail">
        {service.candidates.length === 0 && (
          <span className="nothing">Nog geen fragmenten. Knip er zelf een uit de tekst, of laat de beste momenten zoeken.</span>
        )}
        {service.candidates.map((cand, i) => (
          <button
            key={cand.id}
            className={`mark ${cand.selected ? 'on' : ''} ${playing === cand.id ? 'now' : ''}`
              + ` ${cand.shortlisted ? '' : 'aside'} ${cand.source === 'self' ? 'own' : ''}`}
            style={{
              left: `${(cand.start / duration) * 100}%`,
              width: `${Math.max(1.4, ((cand.end - cand.start) / duration) * 100)}%`,
            }}
            onClick={() => onPick(cand)}
            title={`${cand.source === 'self' ? 'Zelf geknipt · ' : ''}${cand.title}`
              + ` · ${formatTime(cand.start)} tot ${formatTime(cand.end)}`}
          >
            {i + 1}
          </button>
        ))}
        <span className="head" style={{ left: `${(time / duration) * 100}%` }} />
      </div>
      <div className="ticks">
        {[0, 0.25, 0.5, 0.75, 1].map((f) => (
          <span key={f} className="tc muted">{clock(duration * f)}</span>
        ))}
      </div>
    </div>
  )
}
