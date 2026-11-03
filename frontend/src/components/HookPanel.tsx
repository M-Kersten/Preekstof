import type { Hook, Segment } from '../api'
import { wordTimes } from '../subtitleLayout'
import Section from './Section'

interface Props {
  hook: Hook | null
  segments: Segment[]
  currentTime: number
  duration: number
  busy: boolean
  onChange: (hook: Hook | null) => void
  onSuggest: () => void
  onPlay: (start: number, end: number) => void
}

/** A hook is a preview, so it stays short; the server holds the same limits (hooks.py). */
const STEP = 0.1
const LONGEST = 10
const SHORTEST_CLIP = 15

const seconds = (value: number) => `${value.toFixed(1).replace('.', ',')} s`
const clock = (value: number) =>
  `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`
const exact = (value: number) =>
  `${Math.floor(value / 60)}:${(value % 60).toFixed(1).padStart(4, '0').replace('.', ',')}`

/** The words said inside the hook, as the subtitles read now: the same ones the video shows. */
function hookWords(hook: Hook, segments: Segment[]): string {
  return segments
    .flatMap((s) => wordTimes(s))
    .filter((w) => (w.start + w.end) / 2 >= hook.start && (w.start + w.end) / 2 <= hook.end)
    .map((w) => w.word)
    .join(' ')
}

/** The subtitle line playing at `time`, or the first one after it. */
function lineAt(segments: Segment[], time: number): Segment | null {
  const sorted = [...segments].filter((s) => s.text.trim()).sort((a, b) => a.start - b.start)
  return sorted.find((s) => time >= s.start && time < s.end) ?? sorted.find((s) => s.start >= time) ?? null
}

export default function HookPanel({ hook, segments, currentTime, duration, busy, onChange, onSuggest, onPlay }: Props) {
  const tooShort = duration < SHORTEST_CLIP
  const line = lineAt(segments, currentTime)
  const fromLine = line && line.end - line.start <= LONGEST
    ? { start: Math.max(0, line.start - 0.1), end: Math.min(duration, line.end + 0.2) }
    : null

  const take = () => {
    if (!fromLine) return
    onChange({ start: fromLine.start, end: fromLine.end, text: line?.text ?? '', on: true, by: 'hand' })
  }
  const nudge = (edge: 'start' | 'end', by: number) => {
    if (!hook) return
    const next = { ...hook, [edge]: Math.round((hook[edge] + by) * 10) / 10 }
    if (next.start < 0 || next.end > duration || next.end - next.start < 0.5) return
    onChange(next)
  }

  const words = hook ? hookWords(hook, segments) : ''

  return (
    <Section
      title="Hook"
      intro="Een paar seconden uit de clip die vooraan komen: de predikant zegt de kern, een korte witte flits, en dan begint de clip bij het begin."
      className="hook-panel"
    >
      {tooShort ? (
        <p className="hint">Dit fragment is korter dan {SHORTEST_CLIP} seconden. Daar past geen hook voor.</p>
      ) : hook ? (
        <>
          <label className="check">
            <input type="checkbox" checked={hook.on} onChange={(e) => onChange({ ...hook, on: e.target.checked })} />
            <span>Begin de video met deze hook</span>
          </label>
          <blockquote className={`hook-quote ${hook.on ? '' : 'off'}`}>
            {words || <em>Op deze plek staan geen ondertitels.</em>}
          </blockquote>
          <p className="hook-meta">
            {seconds(hook.end - hook.start)} · uit {clock(hook.start)} · {hook.by === 'hand' ? 'zelf gekozen' : 'voorgesteld'}
          </p>
          <div className="hook-row">
            <button className="small" onClick={() => onPlay(hook.start, hook.end)}>Afspelen zoals in de video</button>
            <button className="small bare" disabled={busy} onClick={onSuggest}>{busy ? 'Er wordt gezocht…' : 'Andere laten kiezen'}</button>
            <button className="small bare" disabled={!fromLine} onClick={take} title={line ? `“${line.text}”` : undefined}>
              Huidige ondertitelregel nemen
            </button>
          </div>
          <div className="hook-row nudge">
            <span>Begin <b>{exact(hook.start)}</b></span>
            <button className="small" aria-label="Begin eerder" onClick={() => nudge('start', -STEP)}>−</button>
            <button className="small" aria-label="Begin later" onClick={() => nudge('start', STEP)}>+</button>
            <span>Einde <b>{exact(hook.end)}</b></span>
            <button className="small" aria-label="Einde eerder" onClick={() => nudge('end', -STEP)}>−</button>
            <button className="small" aria-label="Einde later" onClick={() => nudge('end', STEP)}>+</button>
          </div>
        </>
      ) : (
        <>
          <p className="hint">
            {segments.length
              ? 'Er is nog geen hook voor deze clip. Laat er een kiezen, of zet de video op de zin die je wilt en neem die regel.'
              : 'Zodra de ondertitels er zijn, kan er een hook gekozen worden.'}
          </p>
          <div className="hook-row">
            <button className="small" disabled={busy || !segments.length} onClick={onSuggest}>
              {busy ? 'Er wordt gezocht…' : 'Laat een hook kiezen'}
            </button>
            <button className="small bare" disabled={!fromLine} onClick={take} title={line ? `“${line.text}”` : undefined}>
              Huidige ondertitelregel nemen
            </button>
          </div>
        </>
      )}
      {hook && (
        <p className="hint">
          De hook komt uit de clip zelf en is later in de video nog een keer te horen. Met + en − schuif je het begin en
          het einde per tiende seconde.
        </p>
      )}
    </Section>
  )
}
