import { useEffect, useMemo, useRef, useState } from 'react'
import type { Hook, Segment, Spoken } from '../api'
import { EARLIEST, LONGEST, LONGEST_BY_HAND, SHORTEST, hookEdges, leansBack } from '../hook'
import { wordTimes } from '../subtitleLayout'
import Section from './Section'

interface Props {
  hook: Hook | null
  /** What Claude proposed for this clip, the hook in use among them. */
  options: Hook[]
  segments: Segment[]
  duration: number
  busy: boolean
  onChange: (hook: Hook | null) => void
  onSuggest: () => void
  onPlay: (start: number, end: number) => void
}

interface Word extends Spoken {
  line: number
}

const STEP = 0.1
const SHORTEST_CLIP = 15

const seconds = (value: number) => `${value.toFixed(1).replace('.', ',')} s`
const clock = (value: number) =>
  `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`
const exact = (value: number) =>
  `${Math.floor(value / 60)}:${(value % 60).toFixed(1).padStart(4, '0').replace('.', ',')}`
const middle = (w: Spoken) => (w.start + w.end) / 2
const within = (w: Spoken, range: { start: number; end: number }) =>
  middle(w) >= range.start && middle(w) <= range.end
const same = (a: { start: number; end: number }, b: { start: number; end: number }) =>
  Math.abs(a.start - b.start) < 0.005 && Math.abs(a.end - b.end) < 0.005

/** What is worth knowing about a hook of these seconds, or nothing. */
function advice(start: number, end: number, text = ''): string[] {
  const length = end - start
  const said: string[] = []
  const first = leansBack(text)
  if (first) said.push(`Begint met „${first}”: zonder wat ervoor kwam weet de kijker niet waar dat op slaat.`)
  if (length > LONGEST_BY_HAND) said.push('Te lang: een hook duurt hoogstens tien seconden.')
  else if (length > LONGEST) said.push('Lang voor een hook. Na vijf seconden voelt het als een tweede begin.')
  if (length < SHORTEST) said.push('Erg kort. Onder anderhalve seconde is het eerder een woord dan een zin.')
  if (start < EARLIEST) said.push('Dit komt uit het begin van de clip, dus de kijker hoort het meteen daarna nog een keer.')
  return said
}

/**
 * The hook: which few seconds open the video, and the ways to choose them.
 *
 * Claude's choice is a first proposal and nothing more. Its other proposals sit right under
 * it, to play and take with one click. Asking again brings different sentences. And any
 * sentence of the clip can be made the hook by clicking its first and its last word, cut by
 * the same rule the server uses (hook.ts), so what is shown here is what the video gets.
 */
export default function HookPanel({ hook, options, segments, duration, busy, onChange, onSuggest, onPlay }: Props) {
  const words = useMemo<Word[]>(
    () => [...segments]
      .filter((s) => s.text.trim())
      .sort((a, b) => a.start - b.start)
      .flatMap((s, line) => wordTimes(s).map((w) => ({ ...w, line }))),
    [segments])
  const [pending, setPending] = useState<number | null>(null)
  const [hover, setHover] = useState<number | null>(null)
  const [refused, setRefused] = useState('')
  const box = useRef<HTMLDivElement>(null)

  // Esc stops choosing halfway.
  useEffect(() => {
    if (pending === null) return
    const stop = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPending(null)
        setHover(null)
      }
    }
    window.addEventListener('keydown', stop)
    return () => window.removeEventListener('keydown', stop)
  }, [pending])

  // The words of the hook in view, wherever in the clip it is.
  useEffect(() => {
    const list = box.current
    const first = list?.querySelector<HTMLElement>('.word.in')
    if (list && first) list.scrollTop = Math.max(0, first.offsetTop - list.offsetTop - 40)
  }, [hook?.start, hook?.end])

  if (duration < SHORTEST_CLIP) {
    return (
      <Section title="Hook" className="hook-panel">
        <p className="hint">Dit fragment is korter dan {SHORTEST_CLIP} seconden. Daar past geen hook voor.</p>
      </Section>
    )
  }

  const textOf = (range: { start: number; end: number }, fallback = '') =>
    words.filter((w) => within(w, range)).map((w) => w.word).join(' ') || fallback

  // While choosing: from the first word clicked to the one under the pointer.
  const picking = pending !== null
    ? [Math.min(pending, hover ?? pending), Math.max(pending, hover ?? pending)] as const
    : null
  const pickedCut = picking ? hookEdges(words, picking[0], picking[1], duration) : null
  const pickedText = picking ? words.slice(picking[0], picking[1] + 1).map((w) => w.word).join(' ') : ''

  const stopPicking = () => {
    setPending(null)
    setHover(null)
  }

  const pick = (index: number) => {
    setRefused('')
    if (pending === null) {
      setPending(index)
      setHover(index)
      return
    }
    const first = Math.min(pending, index)
    const last = Math.max(pending, index)
    const cut = hookEdges(words, first, last, duration)
    stopPicking()
    if (cut.end - cut.start > LONGEST_BY_HAND) {
      setRefused('Dat is langer dan tien seconden. Kies een kortere zin.')
      return
    }
    onChange({ ...cut, text: words.slice(first, last + 1).map((w) => w.word).join(' '), on: true, by: 'hand' })
  }

  const nudge = (edge: 'start' | 'end', by: number) => {
    if (!hook) return
    const next = { ...hook, [edge]: Math.round((hook[edge] + by) * 10) / 10 }
    if (next.start < 0 || next.end > duration || next.end - next.start < 0.5) return
    onChange(next)
  }

  const others = options.filter((o) => !hook || !same(o, hook))
  const proposed = hook ? options.some((o) => same(o, hook)) : false
  const told = hook ? advice(hook.start, hook.end, textOf(hook, hook.text)) : []

  return (
    <Section
      title="Hook"
      intro="De eerste seconden van de video: de predikant zegt de kern, een korte witte flits, en dan begint de clip bij het begin."
      className="hook-panel"
    >
      {hook ? (
        <>
          <label className="check">
            <input type="checkbox" checked={hook.on} onChange={(e) => onChange({ ...hook, on: e.target.checked })} />
            <span>Begin de video met deze hook</span>
          </label>
          <blockquote className={`hook-quote ${hook.on ? '' : 'off'}`}>
            {textOf(hook, hook.text) || <em>Op deze plek staan geen ondertitels.</em>}
          </blockquote>
          <div className="hook-row">
            <button className="small" onClick={() => onPlay(hook.start, hook.end)}>▶ Bekijk het begin van de video</button>
            <span className="hook-meta">
              {seconds(hook.end - hook.start)} · uit {clock(hook.start)} · {proposed ? 'voorstel' : 'zelf gekozen'}
            </span>
          </div>
          {told.length > 0 && <p className="hook-advice">{told.join(' ')}</p>}
        </>
      ) : (
        <p className="hint">
          {words.length
            ? 'Deze clip heeft nog geen hook. Vraag om voorstellen, of klik hieronder zelf een zin aan.'
            : 'Zodra de ondertitels er zijn, kan er een hook gekozen worden.'}
        </p>
      )}

      {words.length > 0 && (
        <>
          <h3 className="hook-head">{others.length ? 'Andere voorstellen' : 'Voorstellen'}</h3>
          {others.length > 0 && (
            <ul className="hook-options">
              {others.map((o) => (
                <li key={`${o.start}-${o.end}`}>
                  <span className="hook-option-text">“{textOf(o, o.text)}”</span>
                  <span className="hook-meta">{seconds(o.end - o.start)} · {clock(o.start)}</span>
                  <button className="small bare" aria-label="Afspelen" title="Afspelen" onClick={() => onPlay(o.start, o.end)}>▶</button>
                  <button className="small" onClick={() => onChange(o)}>Gebruiken</button>
                </li>
              ))}
            </ul>
          )}
          <div className="hook-row">
            <button className="small bare" disabled={busy} onClick={onSuggest}>
              {busy ? 'Er wordt gezocht…' : options.length ? 'Andere zinnen laten voorstellen' : 'Laat voorstellen doen'}
            </button>
          </div>

          <h3 className="hook-head">Zelf kiezen</h3>
          <p className="hint hook-how">
            {pending === null
              ? 'Klik op het eerste woord van je hook, en daarna op het laatste.'
              : <>Klik nu op het laatste woord, of <button type="button" className="linkish" onClick={stopPicking}>stop</button> (Esc).</>}
          </p>
          <div className={`hook-words ${pending !== null ? 'choosing' : ''}`} ref={box}>
            {words.map((w, i) => {
              const chosen = picking ? i >= picking[0] && i <= picking[1] : Boolean(hook && within(w, hook))
              const lineStart = i === 0 || words[i - 1].line !== w.line
              return (
                <span key={i}>
                  {lineStart && i > 0 && <br />}
                  {lineStart && <span className="at">{clock(w.start)}</span>}
                  <button
                    type="button"
                    className={`word ${chosen ? (picking ? 'picking' : 'in') : ''} ${w.start < EARLIEST ? 'early' : ''}`}
                    aria-pressed={chosen}
                    onClick={() => pick(i)}
                    onMouseEnter={() => pending !== null && setHover(i)}
                  >
                    {w.word}
                  </button>{' '}
                </span>
              )
            })}
          </div>
          {pickedCut && (
            <p className="hook-advice live">
              {seconds(pickedCut.end - pickedCut.start)}. {advice(pickedCut.start, pickedCut.end, pickedText).join(' ')}
            </p>
          )}
          {refused && <p className="hook-advice">{refused}</p>}

          {hook && (
            <details className="hook-fine">
              <summary>Precies afstellen</summary>
              <div className="hook-row nudge">
                <span>Begin <b>{exact(hook.start)}</b></span>
                <button className="small" aria-label="Begin eerder" onClick={() => nudge('start', -STEP)}>−</button>
                <button className="small" aria-label="Begin later" onClick={() => nudge('start', STEP)}>+</button>
                <span>Einde <b>{exact(hook.end)}</b></span>
                <button className="small" aria-label="Einde eerder" onClick={() => nudge('end', -STEP)}>−</button>
                <button className="small" aria-label="Einde later" onClick={() => nudge('end', STEP)}>+</button>
              </div>
              <p className="hint">Per tiende seconde, voor als het eerste of laatste woord net wordt afgekapt.</p>
            </details>
          )}
        </>
      )}
    </Section>
  )
}
