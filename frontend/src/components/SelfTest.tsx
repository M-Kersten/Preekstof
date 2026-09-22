import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type SelfTest as State, type SelfTestStep } from '../api'

const LABEL: Record<string, string> = {
  geluid: 'Geluid uit de video halen',
  uitschrijven: 'De zin terugluisteren',
  volgen: 'De beelden nakijken',
  clip: 'Er een clip van maken',
}

const Row = ({ step }: { step: SelfTestStep }) => (
  <li className={step.skipped ? 'skipped' : step.ok ? 'ok' : 'bad'}>
    <span className="dot" />
    <div>
      <strong>{LABEL[step.step] ?? step.name}</strong>
      <span className="meta">{step.detail}</span>
    </div>
    {!step.skipped && <span className="tc">{step.seconds.toFixed(1)}s</span>}
  </li>
)

/**
 * "Doe de proef" — ten seconds of a spoken sentence through the whole chain.
 *
 * Every other check in this app asks whether a file is in the right place. This one does
 * the work: pulls audio out, loads the speech model, looks through the frames, renders a
 * vertical clip with a caption burned into it. What breaks at a church breaks here, in a
 * minute, instead of twenty minutes into the first real service.
 *
 * The first run on a fresh machine downloads 460 MB of speech model, so this is also where
 * that wait happens, once, at a moment nobody is waiting for a clip.
 */
export default function SelfTest() {
  const [state, setState] = useState<State | null>(null)
  const [error, setError] = useState<string | null>(null)
  const timer = useRef<number | null>(null)

  const load = useCallback(
    () =>
      api
        .selfTest()
        .then(setState)
        .catch(() => setState(null)),
    [],
  )

  useEffect(() => {
    load()
  }, [load])

  // While it runs, keep asking. The job survives a reload, so a page that comes back finds
  // the proof still going rather than a button that pretends nothing is happening.
  const busy = state?.job?.status === 'running'
  useEffect(() => {
    if (!busy) {
      if (timer.current) window.clearInterval(timer.current)
      return
    }
    timer.current = window.setInterval(load, 1200)
    return () => {
      if (timer.current) window.clearInterval(timer.current)
    }
  }, [busy, load])

  const start = async () => {
    setError(null)
    try {
      await api.runSelfTest()
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const last = state?.last
  const progress = Math.round((state?.job?.progress ?? 0) * 100)

  return (
    <div className="proof">
      <div className="asked">
        <div>
          <strong>Werkt alles op deze computer?</strong>
          <p className="hint">
            Tien seconden gesproken tekst door dezelfde molen als een echte dienst: geluid
            eruit, uitschrijven, beelden nakijken, een clip maken. Gaat er iets mis, dan weet
            je binnen een minuut wat. De eerste keer duurt het langer, want dan wordt het
            spraakmodel van 460 MB opgehaald.
          </p>
        </div>
        <button className="small" disabled={busy} onClick={start}>
          {busy ? 'Bezig…' : last ? 'Nog een keer' : 'Doe de proef'}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {busy && (
        <div className="progress busy">
          <div className="bar"><div style={{ width: `${progress}%` }} /></div>
          <div className="label">
            <span>{state?.job?.message ?? 'Bezig'}</span>
            <span>{progress ? `${progress}%` : ''}</span>
          </div>
        </div>
      )}

      {last && !busy && (
        <>
          <ul className="proof-steps">
            {last.steps.map((s) => (
              <Row key={s.step} step={s} />
            ))}
          </ul>
          {last.heard && (
            <p className="hint heard">
              Teruggelezen: <q>{last.heard}</q>
            </p>
          )}
          {state?.hasClip && (
            <video className="proof-clip" src="/selftest/clip" controls playsInline preload="metadata" />
          )}
        </>
      )}
    </div>
  )
}
