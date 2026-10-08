import { useEffect, useState } from 'react'
import type { ClipCandidate, ProcessedClip } from '../api'
import { formatTime } from '../subtitleLayout'
import { type Version, byFragment } from '../versions'

interface Props {
  clips: ProcessedClip[]
  candidates: ClipCandidate[]
  disabled: boolean
  onOpen: (projectId: string) => void
  onRemove: (version: Version, title: string) => void
}

const plural = (n: number, one: string, more: string) => `${n} ${n === 1 ? one : more}`

/**
 * The clips made from this service, in the dock at the bottom of the page. One line per
 * fragment, in the order they come in the service; a fragment made more than once shows its
 * versions under its title, newest first, instead of the same title twice.
 */
export default function MadeClips({ clips, candidates, disabled, onOpen, onRemove }: Props) {
  const [open, setOpen] = useState(false)
  const made = byFragment(clips, candidates)

  useEffect(() => {
    if (!open) return
    const close = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [open])

  if (made.length === 0) return null
  const versions = clips.length - made.length

  // One clip needs no list: it gets its button right here.
  if (made.length === 1 && made[0].versions.length === 1) {
    const only = made[0].versions[0]
    return (
      <div className="ready single">
        <span className="ready-says">✓ Klaar om te bewerken</span>
        <span className="ready-title">{made[0].title}</span>
        <button className="small" onClick={() => onOpen(only.projectId)}>Bewerken →</button>
      </div>
    )
  }

  return (
    <div className="ready">
      {open && (
        <ul className="made-list" aria-label="Clips uit deze dienst">
          {made.map((fragment) => (
            <li key={fragment.key}>
              <div className="made-head">
                <strong>{fragment.title}</strong>
                {fragment.versions.length > 1 && <span className="meta">{fragment.versions.length} versies</span>}
              </div>
              {fragment.versions.map((v) => (
                <div key={v.projectId} className={`made-version ${v.latest ? 'latest' : ''}`}>
                  <span className="tc">{formatTime(v.start)} – {formatTime(v.end)}</span>
                  <span className="meta">{Math.round(v.end - v.start)} s</span>
                  {fragment.versions.length > 1 && (
                    <span className="meta">
                      {v.latest ? 'nieuwste' : `versie ${v.number}`}
                      {v.copy ? ' · zelfde begin en einde' : ''}
                    </span>
                  )}
                  <span className="made-acts">
                    {fragment.versions.length > 1 && (
                      <button className="small bare" disabled={disabled} onClick={() => onRemove(v, fragment.title)}
                              title="Deze versie weggooien">
                        Weghalen
                      </button>
                    )}
                    <button className="small" onClick={() => onOpen(v.projectId)}>Bewerken →</button>
                  </span>
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}
      {/* Below the list, so the button stays where it was when the list opens upwards. */}
      <div className="ready-row">
        <button className="ready-toggle bare" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="ready-says">✓ {plural(made.length, 'fragment', 'fragmenten')} klaar om te bewerken</span>
          {versions > 0 && <span className="meta"> · {plural(versions, 'extra versie', 'extra versies')}</span>}
          <span className="ready-open">{open ? 'Verbergen ▾' : 'Bekijken ▴'}</span>
        </button>
      </div>
    </div>
  )
}
