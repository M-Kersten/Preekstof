import { useEffect, useState } from 'react'
import { setupApi, type SetupState } from './api'
import { remember, remembered } from './remember'
import { useChurch } from './church'
import BrandPanel, { type BrandTab } from './components/BrandPanel'
import ClipEditor from './components/ClipEditor'
import ServiceView from './components/ServiceView'
import StoragePanel from './components/StoragePanel'
import SystemCheck from './components/SystemCheck'
import Welcome from './components/Welcome'

type Mode = 'clip' | 'service'
const MODE_KEY = 'mode'

/** A wide recording split into parts: the whole service. */
const ServiceIcon = () => (
  <svg width="17" height="17" viewBox="0 0 17 17" fill="none" aria-hidden="true">
    <rect x="1.4" y="4.2" width="14.2" height="8.6" rx="1.6" stroke="currentColor" strokeWidth="1.4" />
    <path d="M6.1 4.2v8.6M10.9 4.2v8.6" stroke="currentColor" strokeWidth="1.4" />
  </svg>
)

/** One upright 9:16 fragment: a single clip. */
const ClipIcon = () => (
  <svg width="17" height="17" viewBox="0 0 17 17" fill="none" aria-hidden="true">
    <rect x="4.6" y="1.4" width="7.8" height="14.2" rx="1.6" stroke="currentColor" strokeWidth="1.4" />
    <path d="m7.5 6.2 3.2 2.3-3.2 2.3z" fill="currentColor" />
  </svg>
)

/** Sliders: what you set once for the church and then leave alone. */
const BrandIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M2 4.6h12M2 11.4h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    <circle cx="5.8" cy="4.6" r="1.9" fill="currentColor" />
    <circle cx="10.4" cy="11.4" r="1.9" fill="currentColor" />
  </svg>
)

/** A bin: making room on the disk. */
const TidyIcon = () => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
    <path d="M2.6 4.3h10.8M6.2 4.3V3c0-.4.3-.8.7-.8h2.2c.4 0 .7.4.7.8v1.3"
          stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    <path d="M4 4.3h8l-.6 8.4c0 .6-.5 1.1-1.1 1.1H5.7c-.6 0-1.1-.5-1.1-1.1z"
          stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
  </svg>
)

/** The shipped default is not a church's name and must not read as one in the bar. */
const named = (name: string | undefined) =>
  !name || name === 'Example Church' ? 'Nog niet ingesteld' : name


export default function App() {
  const [mode, setMode] = useState<Mode>(() => (remembered(MODE_KEY) === 'clip' ? 'clip' : 'service'))
  const [projectId, setProjectId] = useState<string | null>(null)
  const [tidying, setTidying] = useState(false)
  const [branding, setBranding] = useState(false)
  const [brandTab, setBrandTab] = useState<BrandTab>('church')
  const [setup, setSetup] = useState<SetupState | null>(null)
  const church = useChurch()

  // Whether this church has been through the welcome yet. Until the answer is in, the page
  // stays blank: flashing the upload box at somebody and then replacing it with a welcome
  // is worse than half a second of nothing.
  useEffect(() => {
    setupApi
      .read()
      .then(setSetup)
      // A backend that cannot answer is not a reason to trap anyone on a welcome screen.
      .catch(() => setSetup({ done: true, version: '', provider: '', hasKey: true, churchName: '',
                              station: '', skippedStation: false, missing: [] }))
  }, [])

  // Other parts of the page can send you here, on the tab that holds what they meant.
  useEffect(() => {
    const open = (e: Event) => {
      setBrandTab(((e as CustomEvent).detail as BrandTab) ?? 'church')
      setBranding(true)
    }
    window.addEventListener('open-brand', open)
    return () => window.removeEventListener('open-brand', open)
  }, [])

  const switchMode = (next: Mode) => {
    setMode(next)
    remember(MODE_KEY, next)
  }

  const openClip = (id: string) => {
    setProjectId(id)
    switchMode('clip')
  }

  if (!setup) return null
  if (!setup.done) {
    return (
      <>
        <header className="appbar bare-bar">
          <div className="brand">
            <span className="logo" aria-hidden="true" />
            <div>
              <div className="name">Preekstof</div>
              <div className="church">{named(church?.churchName)}</div>
            </div>
          </div>
        </header>
        {/* Not .page: the welcome uses the whole window, not a column in the middle. */}
        <main>
          <Welcome state={setup} onDone={setSetup} />
        </main>
      </>
    )
  }

  return (
    <>
      <header className="appbar">
        <div className="brand">
          {/* The mark is one colour, so it is painted through rather than dropped in:
              purple on the dark bar would be a smudge. */}
          <span className="logo" aria-hidden="true" />
          <div>
            <div className="name">Preekstof</div>
            <div className="church">{named(church?.churchName)}</div>
          </div>
        </div>

        {/* Where you are. One switch between two workspaces, so it cannot read as a menu. */}
        <nav className="pages" aria-label="Waar wil je aan werken">
          <button
            className={mode === 'service' ? 'on' : ''}
            aria-current={mode === 'service' ? 'page' : undefined}
            onClick={() => switchMode('service')}
          >
            <ServiceIcon /> Hele dienst
          </button>
          <button
            className={mode === 'clip' ? 'on' : ''}
            aria-current={mode === 'clip' ? 'page' : undefined}
            onClick={() => switchMode('clip')}
          >
            <ClipIcon /> Losse clip
          </button>
        </nav>

        <SystemCheck />

        {/* Things that open on top of your work and close again. Outlined, never filled, so
            they cannot be mistaken for the page you are on. */}
        <div className="tools">
          <button
            aria-haspopup="dialog"
            title="De gegevens van de kerk, de woorden die hier vallen en het eindscherm achter elke video"
            onClick={() => {
              setBrandTab('church')
              setBranding(true)
            }}
          >
            <BrandIcon /> <span>Merk instellen</span>
          </button>
          <button
            aria-haspopup="dialog"
            title="Kijken wat de opnames op de schijf innemen, en oude weggooien"
            onClick={() => setTidying(true)}
          >
            <TidyIcon /> <span>Ruimte vrijmaken</span>
          </button>
          <button
            className="bare small"
            title="De stappen van het begin nog eens langslopen"
            onClick={() => setupApi.reopen().then(setSetup).catch(() => undefined)}
          >
            Instellen opnieuw
          </button>
        </div>
      </header>
      <main className="page">
        {mode === 'service' ? <ServiceView onOpenClip={openClip} /> : <ClipEditor projectId={projectId} onProjectChange={setProjectId} />}
      </main>
      {branding && <BrandPanel tab={brandTab} onClose={() => setBranding(false)} />}
      {tidying && <StoragePanel onClose={() => setTidying(false)} />}
    </>
  )
}
