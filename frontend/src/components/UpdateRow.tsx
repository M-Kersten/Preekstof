import { useCallback, useEffect, useState } from 'react'
import { api, type UpdateState } from '../api'

interface Props {
  state: UpdateState
  onChange: (state: UpdateState) => void
}

/**
 * A newer version, in the readiness panel. Bijwerken fetches the download for this computer
 * and puts it next to the app; nothing changes until the app starts again, which one more
 * click does. The church's own work is in its own folder and stays where it is.
 */
export default function UpdateRow({ state, onChange }: Props) {
  const [error, setError] = useState<string | null>(null)
  const [restarting, setRestarting] = useState(false)
  const busy = state.job?.status === 'running'

  const refresh = useCallback(() => api.update().then(onChange).catch(() => undefined), [onChange])
  useEffect(() => {
    if (!busy) return
    const handle = setInterval(refresh, 1000)
    return () => clearInterval(handle)
  }, [busy, refresh])

  const start = async () => {
    setError(null)
    try {
      await api.startUpdate()
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const restart = async () => {
    setError(null)
    try {
      await api.restartForUpdate()
      setRestarting(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  // Once the server is back with another version, the page that belongs to it is loaded.
  useEffect(() => {
    if (!restarting) return
    const before = state.running
    const handle = setInterval(() => {
      api.health().then((h) => {
        if (!h.version.startsWith(before)) window.location.reload()
      }).catch(() => undefined)
    }, 1500)
    return () => clearInterval(handle)
  }, [restarting, state.running])

  if (restarting) {
    return (
      <li>
        <div className="restarting" role="status">
          <div>
            <strong>Preekstof start opnieuw met versie {state.staged}</strong>
            <p>Dit scherm laadt vanzelf opnieuw zodra de nieuwe versie draait. Laat het zwarte venster open.</p>
          </div>
        </div>
      </li>
    )
  }

  const failed = state.job?.status === 'error' ? state.job.error : null
  const latest = state.latest
  return (
    <li className="syscheck-update">
      <span className="dot" />
      <div>
        {state.staged ? (
          <>
            <strong>Versie {state.staged} staat klaar</strong>
            <span className="meta">
              {state.canRestart
                ? 'Hij gaat erin zodra de app opnieuw start. Je eigen werk blijft staan.'
                : 'Sluit het zwarte venster en start Preekstof opnieuw; dan gaat hij erin.'}
            </span>
          </>
        ) : (
          <>
            <strong>Versie {latest?.version} is er</strong>
            <span className="meta">
              {busy ? state.job?.message || 'Wordt opgehaald …' : latest?.headline || 'Een nieuwere versie van Preekstof.'}
            </span>
            {state.why && <span className="meta">{state.why}</span>}
          </>
        )}
        {(error || failed) && <span className="trouble">{error || failed}</span>}
      </div>
      {state.staged ? (
        state.canRestart && <button className="small primary" onClick={restart}>Nu opnieuw starten</button>
      ) : state.why ? (
        <a className="small-link" href={latest?.url} target="_blank" rel="noreferrer">Ophalen ↗</a>
      ) : (
        <button className="small" disabled={busy} onClick={start}>
          {busy ? `${Math.round((state.job?.progress ?? 0) * 100)}%` : 'Bijwerken'}
        </button>
      )}
    </li>
  )
}
