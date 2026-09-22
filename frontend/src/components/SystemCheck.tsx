import { useEffect, useRef, useState } from 'react'
import { api, type Health } from '../api'
import Report from './Report'

/** Shows whether the app has everything it needs. Opens by itself when something is wrong. */
export default function SystemCheck({ onProve }: { onProve: () => void }) {
  const [report, setReport] = useState<Health | null>(null)
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  // Clicking anywhere else closes the panel.
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  useEffect(() => {
    let alive = true
    const load = () =>
      api
        .health()
        .then((r) => {
          if (!alive) return
          setReport(r)
          if (!r.ok) setOpen(true)
        })
        .catch(() => alive && setReport(null))
    load()
    const handle = setInterval(load, 60000)
    return () => {
      alive = false
      clearInterval(handle)
    }
  }, [])

  if (!report) return null

  const failing = report.checks.filter((c) => !c.ok)
  return (
    <div className="syscheck" ref={box}>
      <button className={`bare pill ${report.ok ? 'ok' : 'bad'}`} onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="dot" />
        {report.ok ? 'Alles gereed' : failing.length === 1 ? '1 punt nog niet in orde' : `${failing.length} punten nog niet in orde`}
      </button>
      {open && (
        <ul className="syscheck-list">
          {report.checks.map((c) => (
            <li key={c.name} className={c.ok ? 'ok' : 'bad'}>
              <span className="dot" />
              <strong>{c.name}</strong>
              <span>{c.detail}</span>
            </li>
          ))}
          {/* The first question on every support call, in the panel somebody already opens
              when something is wrong. Next to it, the thing to send along: a volunteer who
              has got this far has already been told something is not right. */}
          {/* Every row above says whether a file is where it should be. None of them says
              whether the work runs, and that is a different question with a worse answer. */}
          <li className="syscheck-prove">
            <span className="dot" />
            <div>
              <strong>Doe de proef</strong>
              <span className="meta">Tien seconden door de hele molen, zodat je het weet voordat het telt.</span>
            </div>
            <button className="small" onClick={() => { setOpen(false); onProve() }}>Starten</button>
          </li>
          <li className="syscheck-version">
            <span>Preekstof {report.version}</span>
            <Report trouble={failing.length
              ? `Gemeld vanuit het gereedheidspaneel. Niet in orde: ${failing.map((c) => c.name).join(', ')}.`
              : 'Gemeld vanuit het gereedheidspaneel, terwijl alle controles op groen stonden.'} />
          </li>
        </ul>
      )}
    </div>
  )
}
