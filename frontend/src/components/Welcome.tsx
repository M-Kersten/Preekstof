import { useState } from 'react'
import { ApiError, serviceApi, setupApi, type SetupState, type StationService } from '../api'
import { announceBrandChange } from '../church'

interface Props {
  state: SetupState
  onDone: (state: SetupState) => void
}

type Step = 'why' | 'key' | 'church' | 'station' | 'ready'

const ORDER: Step[] = ['why', 'key', 'church', 'station', 'ready']
const LABEL: Record<Step, string> = {
  why: 'Wat dit is',
  key: 'Claude-sleutel',
  church: 'Jullie kerk',
  station: 'Kerkdienstgemist',
  ready: 'Beginnen',
}

function say(e: unknown): string {
  if (e instanceof ApiError) return e.message
  return e instanceof Error ? e.message : String(e)
}

/**
 * What the app makes, in one look: a wide recording, and the upright clip that comes out
 * of it with the words on screen.
 *
 * Drawn rather than described, because it is the one thing a sentence keeps failing to
 * land. Flat fills from the palette, no gradients and no arrows: the overlap and the
 * change of shape carry it.
 */
const WhatItMakes = () => (
  <svg className="scene" viewBox="0 0 280 190" role="img"
       aria-label="Een brede opname van een dienst, en de rechtopstaande clip die eruit komt">
    {/* the service as it was recorded */}
    <rect x="2" y="34" width="190" height="107" rx="9" fill="#EDE7F3" />
    <g fill="#4B1E78" opacity="0.28">
      <rect x="28" y="76" width="7" height="23" rx="3.5" />
      <rect x="44" y="66" width="7" height="43" rx="3.5" />
      <rect x="60" y="82" width="7" height="11" rx="3.5" />
      <rect x="76" y="59" width="7" height="57" rx="3.5" />
      <rect x="92" y="73" width="7" height="29" rx="3.5" />
      <rect x="108" y="80" width="7" height="15" rx="3.5" />
      <rect x="124" y="63" width="7" height="49" rx="3.5" />
    </g>
    {/* the clip that comes out of it */}
    <g>
      <rect x="168" y="6" width="104" height="178" rx="12" fill="#FFFFFF" stroke="#E4DCEC" />
      <rect x="176" y="14" width="88" height="140" rx="7" fill="#2A1140" />
      <path d="M213 74l16 10-16 10z" fill="#C9971C" />
      <rect x="186" y="126" width="68" height="7" rx="3.5" fill="#FFFFFF" opacity="0.92" />
      <rect x="198" y="138" width="44" height="7" rx="3.5" fill="#C9971C" />
      <rect x="186" y="164" width="52" height="6" rx="3" fill="#E4DCEC" />
    </g>
  </svg>
)

/**
 * The first five minutes, for a church nobody here can see.
 *
 * Someone opens this on a Monday morning. They did not install it, they cannot open a
 * terminal, and if the first thing they meet is an empty upload box they will close the
 * window again. So the app says what it is, asks the three things it cannot work without,
 * and checks each answer on the spot rather than twenty minutes later.
 *
 * Nothing here is a dead end. The church can be typed by hand, kerkdienstgemist can be
 * skipped outright, and everything asked stays editable under Merk instellen.
 */
export default function Welcome({ state, onDone }: Props) {
  const [step, setStep] = useState<Step>(state.missing.includes('key') ? 'why' : 'church')
  const [now, setNow] = useState(state)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [key, setKey] = useState('')
  const [name, setName] = useState(state.churchName === 'Example Church' ? '' : state.churchName)
  const [times, setTimes] = useState('')
  const [insta, setInsta] = useState('')
  const [station, setStation] = useState(state.station)
  const [found, setFound] = useState<{ name: string; services: StationService[] } | null>(null)

  const at = ORDER.indexOf(step)
  const go = (next: Step) => {
    setError(null)
    setStep(next)
  }

  const attempt = async (what: () => Promise<SetupState>, next: Step) => {
    setBusy(true)
    setError(null)
    try {
      setNow(await what())
      announceBrandChange()
      go(next)
    } catch (e) {
      setError(say(e))
    } finally {
      setBusy(false)
    }
  }

  const saveKey = () => attempt(() => setupApi.saveKey(key.trim()), 'church')
  const saveChurch = () => attempt(() => setupApi.saveChurch({
    churchName: name.trim(),
    serviceTimes: times.split(',').map((t) => t.trim()).filter(Boolean),
    instagram: insta.trim(),
  }), 'station')

  /** Look the number up before saving it, so a wrong one says so here and not next Sunday. */
  const lookUp = async () => {
    const id = station.trim()
    if (!id) return
    setBusy(true)
    setError(null)
    setFound(null)
    try {
      const answer = await serviceApi.station(id)
      setFound({ name: answer.name, services: answer.services })
    } catch (e) {
      setError(say(e))
    } finally {
      setBusy(false)
    }
  }

  const saveStation = () => attempt(() => setupApi.saveChurch({ station: station.trim() }), 'ready')
  const finish = (skipped: boolean) => attempt(() => setupApi.done(skipped), 'ready')

  return (
    <div className="welcome">
      <div className="welcome-where">
        <span>{LABEL[step]}</span>
        <span className="meta">{at + 1} / {ORDER.length}</span>
      </div>
      <div className="welcome-rail" aria-hidden="true">
        <span style={{ width: `${(at / (ORDER.length - 1)) * 100}%` }} />
      </div>

      <div className="welcome-body">
        {step === 'why' && (
          <div className="welcome-split">
            <div>
              <h1>Een dienst van anderhalf uur, en de drie minuten die iemand afkijkt</h1>
              <p className="lead">
                Preekstof schrijft de opname uit, leest de preek door en stelt de momenten voor
                die als losse video werken. Jij luistert na en kiest.
              </p>
              <ul className="plain">
                <li>Video en geluid blijven op deze computer.</li>
                <li>Ondertitels, kader en eindscherm gaan vanzelf mee.</li>
                <li>Elk voorstel kun je bijstellen, weggooien of zelf uitknippen.</li>
              </ul>
              <div className="acts">
                <button className="primary" onClick={() => go('key')}>Aan de slag</button>
                <span className="meta">Drie vragen, een paar minuten</span>
              </div>
            </div>
            <WhatItMakes />
          </div>
        )}

        {step === 'key' && (
          <div className="welcome-one">
            <h1>Een sleutel voor Claude</h1>
            <p className="lead">
              Het doorlezen van de preek gebeurt door Claude. Daar heeft de kerk een eigen sleutel
              voor nodig. Reken op <strong>drie cent per dienst</strong>. Uitschrijven, knippen en
              ondertitelen kost niets en gebeurt hier.
            </p>
            <label htmlFor="key">Plak hem hieronder</label>
            <input
              id="key"
              type="password"
              value={key}
              autoComplete="off"
              spellCheck={false}
              placeholder="sk-ant-..."
              onChange={(e) => setKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && key.trim() && saveKey()}
            />
            <p className="hint">
              Nog geen sleutel? Maak een account op{' '}
              <a href="https://console.anthropic.com/" target="_blank" rel="noreferrer">console.anthropic.com</a>,
              zet er wat tegoed op en maak er een aan onder API keys.
            </p>
            {now.hasKey && !error && <p className="good">Er staat al een werkende sleutel klaar.</p>}
            <div className="acts">
              <button className="primary" disabled={busy || !key.trim()} onClick={saveKey}>
                {busy ? 'Even proberen…' : 'Uitproberen en bewaren'}
              </button>
              {now.hasKey && <button onClick={() => go('church')}>Deze houden</button>}
              <button className="quiet" onClick={() => go('church')}>Later</button>
            </div>
          </div>
        )}

        {step === 'church' && (
          <div className="welcome-one">
            <h1>Van welke kerk is dit?</h1>
            <p className="lead">
              Dit komt op het eindscherm achter elke video. Later aanpassen kan altijd.
            </p>
            <label htmlFor="cname">Naam van de kerk</label>
            <input id="cname" value={name} placeholder="Nieuwe Kerk Utrecht"
                   onChange={(e) => setName(e.target.value)} />
            <div className="two">
              <div>
                <label htmlFor="ctimes">Diensttijden</label>
                <input id="ctimes" value={times} placeholder="10:00 Wittevrouwen, 11:30 Wilhelminapark"
                       onChange={(e) => setTimes(e.target.value)} />
              </div>
              <div>
                <label htmlFor="cinsta">Instagram</label>
                <input id="cinsta" value={insta} placeholder="@nieuwekerk_utrecht"
                       onChange={(e) => setInsta(e.target.value)} />
              </div>
            </div>
            <p className="hint">Diensttijden scheid je met een komma. Allebei niet verplicht.</p>
            <div className="acts">
              <button className="primary" disabled={busy || !name.trim()} onClick={saveChurch}>Verder</button>
              <button className="quiet" onClick={() => go('key')}>Terug</button>
            </div>
          </div>
        )}

        {step === 'station' && (
          <div className="welcome-one">
            <h1>Staan jullie diensten op Kerkdienstgemist?</h1>
            <p className="lead">
              Dan haalt de app de opname zelf op en hoef je niets te uploaden. Het nummer staat in
              de adresbalk van jullie eigen pagina.
            </p>
            <p className="address">
              kerkdienstgemist.nl/stations/<mark>1341</mark>/events
            </p>
            <label htmlFor="station">Jullie nummer</label>
            <div className="two-up">
              <input
                id="station"
                value={station}
                inputMode="numeric"
                placeholder="1341"
                onChange={(e) => {
                  setStation(e.target.value)
                  setFound(null)
                }}
                onKeyDown={(e) => e.key === 'Enter' && lookUp()}
              />
              <button disabled={busy || !station.trim()} onClick={lookUp}>
                {busy ? 'Opzoeken…' : 'Opzoeken'}
              </button>
            </div>
            {found && (
              <p className="good">
                {found.name}
                {found.services.length > 0
                  ? ` · ${found.services.length} diensten staan klaar, de laatste is ${found.services[0].title}`
                  : ' · gevonden, er staan nu geen diensten op'}
              </p>
            )}
            <div className="acts">
              <button className="primary" disabled={busy || !found} onClick={saveStation}>
                Dit is onze kerk
              </button>
              <button className="quiet" disabled={busy} onClick={() => finish(true)}>
                Wij staan daar niet op
              </button>
            </div>
          </div>
        )}

        {step === 'ready' && (
          <div className="welcome-split">
            <div>
              <h1>{now.churchName && now.churchName !== 'Example Church'
                ? `Klaar, ${now.churchName}`
                : 'Klaar om te beginnen'}</h1>
              <p className="lead">
                Sleep de opname van een dienst naar binnen, of kies er een uit de lijst. Terwijl
                hij wordt uitgeschreven kun je de tekst al doorlezen en zelf iets uitknippen.
              </p>
              <ul className="plain">
                <li>Uitschrijven duurt een tijdje. Laat het zwarte venster openstaan.</li>
                <li>Momenten zoeken duurt ongeveer een minuut.</li>
                <li>Eindscherm, ondertitelstijl en woordenlijst staan onder Merk instellen.</li>
              </ul>
              <div className="acts">
                <button className="primary" disabled={busy}
                        onClick={async () => {
                          setBusy(true)
                          try {
                            onDone(await setupApi.done(now.skippedStation || !station.trim()))
                          } catch (e) {
                            setError(say(e))
                            setBusy(false)
                          }
                        }}>
                  Naar de app
                </button>
              </div>
            </div>
            <WhatItMakes />
          </div>
        )}

        {error && <div className="error welcome-error">{error}</div>}
      </div>

      <p className="welcome-foot">
        Preekstof {now.version}
        {step !== 'ready' && (
          <>
            {' · '}
            <button className="quiet" onClick={() => finish(now.skippedStation)}>
              Overslaan, ik stel het zelf in
            </button>
          </>
        )}
      </p>
    </div>
  )
}
