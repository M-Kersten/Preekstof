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
  key: 'Sleutel',
  church: 'Jullie kerk',
  station: 'Kerkdienstgemist',
  ready: 'Klaar',
}

function say(e: unknown): string {
  if (e instanceof ApiError) return e.message
  return e instanceof Error ? e.message : String(e)
}

/**
 * A reel, drawn on the dark panel: the wide recording behind it, and in front the upright
 * clip with a word lit up in the caption.
 *
 * That lit word is what this app actually does to a sentence, and no other welcome screen
 * has it. No figure, because a circle with shoulders under it is the icon every app uses
 * for "a user" and it would say nothing about a preacher. Flat fills, tuned for the deep
 * purple it sits on.
 */
const Reel = () => (
  <svg className="reel" viewBox="0 0 220 204" role="img"
       aria-label="De brede opname van een dienst, en de rechtopstaande clip met ondertiteling die eruit komt">
    {/* the recording as it came in, wide and long */}
    <rect x="0" y="62" width="132" height="76" rx="8" fill="#FFFFFF" opacity="0.07" />
    <g fill="#EDE6F4" opacity="0.32">
      <rect x="16" y="91" width="6" height="18" rx="3" />
      <rect x="30" y="83" width="6" height="34" rx="3" />
      <rect x="44" y="96" width="6" height="8" rx="3" />
      <rect x="58" y="77" width="6" height="46" rx="3" />
      <rect x="72" y="89" width="6" height="22" rx="3" />
      <rect x="86" y="95" width="6" height="10" rx="3" />
    </g>
    {/* the clip it becomes. Light housing, so the shape reads at a glance on the dark. */}
    <rect x="112" y="6" width="104" height="192" rx="16" fill="#EDE6F4" />
    <rect x="119" y="13" width="90" height="178" rx="11" fill="#1A0B28" />
    {/* light falling on somebody, without drawing a person */}
    <ellipse cx="164" cy="82" rx="44" ry="40" fill="#FFFFFF" opacity="0.055" />
    {/* the caption, with the word being said lit up */}
    <rect x="130" y="138" width="31" height="10" rx="5" fill="#FFFFFF" opacity="0.9" />
    <rect x="165" y="138" width="33" height="10" rx="5" fill="#C9971C" />
    <rect x="130" y="154" width="25" height="10" rx="5" fill="#FFFFFF" opacity="0.9" />
    <rect x="159" y="154" width="29" height="10" rx="5" fill="#FFFFFF" opacity="0.9" />
    <rect x="130" y="177" width="68" height="3" rx="1.5" fill="#FFFFFF" opacity="0.2" />
    <rect x="130" y="177" width="26" height="3" rx="1.5" fill="#C9971C" />
  </svg>
)

/**
 * The first five minutes, for whoever does the socials at a church.
 *
 * They open this on a Monday. They did not install it, they cannot open a terminal, and an
 * empty upload box tells them nothing. So it says what it is in their own terms, asks the
 * three things it cannot work without, and checks each answer straight away.
 *
 * The two ends are on the dark panel and the three questions in between are light, so the
 * work looks like work and the pitch looks like a pitch. Nothing is a dead end: the church
 * can be typed by hand, kerkdienstgemist can be skipped, and it is all editable later.
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
  const dark = step === 'why' || step === 'ready'
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

  /** Look it up before saving, so a verkeerd nummer says so here and not volgende zondag. */
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
  const church = now.churchName && now.churchName !== 'Example Church' ? now.churchName : ''

  return (
    <div className="welcome">
      <div className="welcome-where">
        <span>{LABEL[step]}</span>
        <span className="welcome-rail" aria-hidden="true">
          <span style={{ width: `${(at / (ORDER.length - 1)) * 100}%` }} />
        </span>
        <span className="tc">{at + 1}/{ORDER.length}</span>
      </div>

      <div className={`panel ${dark ? 'dim' : ''}`}>
        {step === 'why' && (
          <div className="spread">
            <div>
              <h1>Er moet weer iets online van zondag</h1>
              <p className="lead">
                Je weet meestal wel welk stuk je zoekt. Het terugvinden is het werk, en daarna
                moet het nog geknipt en ondertiteld worden. Preekstof neemt dat over. Jij
                luistert na en zegt wat eruit mag.
              </p>
              <p className="aside">
                De opname blijft op deze computer staan. Alleen de uitgeschreven tekst gaat naar
                Claude, om de goede stukken te vinden.
              </p>
              <div className="acts">
                <button className="primary" onClick={() => go('key')}>Aan de slag</button>
                <span className="soft">Kost je een paar minuten</span>
              </div>
            </div>
            <Reel />
          </div>
        )}

        {step === 'key' && (
          <div className="column">
            <h1>Eerst een sleutel van Claude</h1>
            <p className="lead">
              Claude leest de preek door en zoekt de stukken die op zichzelf staan. Daar heb je
              een eigen sleutel voor nodig. Reken op drie cent per dienst. Uitschrijven en knippen
              gebeurt hier op de computer en kost niets.
            </p>
            <label htmlFor="key">Plak je sleutel hier</label>
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
              Heb je er nog geen? Maak een account op{' '}
              <a href="https://console.anthropic.com/" target="_blank" rel="noreferrer">console.anthropic.com</a>,
              zet er wat tegoed op en klik daarna op API keys.
            </p>
            {now.hasKey && !error && <p className="good">Er staat al een sleutel klaar die het doet.</p>}
            <div className="acts">
              <button className="primary" disabled={busy || !key.trim()} onClick={saveKey}>
                {busy ? 'Even proberen…' : 'Uitproberen en bewaren'}
              </button>
              {now.hasKey && <button onClick={() => go('church')}>Die houden</button>}
              <button className="quiet" onClick={() => go('church')}>Doe ik later</button>
            </div>
          </div>
        )}

        {step === 'church' && (
          <div className="column">
            <h1>Hoe heet jullie kerk?</h1>
            <p className="lead">
              Die naam komt onder elke video te staan, met de diensttijden en jullie Instagram
              erbij. Aanpassen kan later ook nog.
            </p>
            <label htmlFor="cname">Naam</label>
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
            <p className="hint">Meer tijden? Zet er een komma tussen. Allebei mag je leeg laten.</p>
            <div className="acts">
              <button className="primary" disabled={busy || !name.trim()} onClick={saveChurch}>Verder</button>
              <button className="quiet" onClick={() => go('key')}>Terug</button>
            </div>
          </div>
        )}

        {step === 'station' && (
          <div className="column">
            <h1>Staan jullie diensten op Kerkdienstgemist?</h1>
            <p className="lead">
              Dan hoef je nooit iets te uploaden, want de app haalt de dienst zelf op. Ga naar
              jullie eigen pagina daar en kijk in de adresbalk. Achter <code>/stations/</code>
              {' '}staat een nummer.
            </p>
            <p className="address">
              kerkdienstgemist.nl/stations/<mark>1341</mark>/events
            </p>
            <label htmlFor="station">Dat nummer</label>
            <div className="beside">
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
                {busy ? 'Even kijken…' : 'Opzoeken'}
              </button>
            </div>
            {found && (
              <p className="good">
                {found.name}
                {found.services.length > 0
                  ? ` · ${found.services.length} diensten staan er klaar. De laatste is ${found.services[0].title}.`
                  : ' · gevonden, alleen staan er nu geen diensten op.'}
              </p>
            )}
            <div className="acts">
              <button className="primary" disabled={busy || !found} onClick={saveStation}>
                Ja, dat is ons
              </button>
              <button className="quiet" disabled={busy} onClick={() => finish(true)}>
                Wij staan daar niet op
              </button>
            </div>
          </div>
        )}

        {step === 'ready' && (
          <div className="spread">
            <div>
              <h1>{church ? `Klaar, ${church}` : 'Klaar'}</h1>
              <p className="lead">
                Zet er maar een dienst in. Terwijl hij wordt uitgeschreven kun je de tekst al
                doorlezen en zelf een stuk uitknippen.
              </p>
              <p className="aside">
                Uitschrijven duurt even. Laat het zwarte venster gewoon openstaan. Het eindscherm
                en de ondertitels regel je later onder Merk instellen.
              </p>
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
            <Reel />
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
              Sla over, ik zoek het zelf wel uit
            </button>
          </>
        )}
      </p>
    </div>
  )
}
