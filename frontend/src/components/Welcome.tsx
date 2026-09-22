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
 * A clip playing, with the word being said lighting up as it goes.
 *
 * The app really does this to a caption, so the welcome does it too rather than describe
 * it. Anybody who has asked their machine to calm down gets the still frame instead.
 */
const Playing = () => (
  <figure className="mock reel">
    <div className="upright">
      <div className="screen">
        <span className="spot" aria-hidden="true" />
        <p className="caption">
          <span>Rust</span> <span>is</span> <span>geen</span> <span>zwakte</span>
        </p>
        <span className="scrub" aria-hidden="true"><span /></span>
      </div>
    </div>
    <figcaption>Ondertiteld, rechtop, klaar om te posten</figcaption>
  </figure>
)

/**
 * What the sleutel buys, laid out the way the suggestion list really is: numbered in the
 * margin, the strongest first, with a mark on the one that would be posted.
 *
 * No coloured bar down the side of the cards. That says nothing a number in the margin
 * does not say better, and it is the first thing a page reaches for when it has no idea
 * what it wants to point at.
 */
const Moments = () => (
  <figure className="mock moments">
    {[
      { title: 'Rust is geen zwakte', when: '22:20 – 23:20', secs: '60 sec', why: 'Begint bij het onderwerp zelf' },
      { title: 'Wat als loslaten de plek is', when: '36:00 – 37:10', secs: '70 sec', why: 'Maakt de gedachte af' },
      { title: 'De vrouw die niet durft te stoppen', when: '29:56 – 31:10', secs: '74 sec', why: 'Een verhaal met een clou' },
    ].map((m, i) => (
      <div key={m.title} className="moment">
        <span className="no tc">{String(i + 1).padStart(2, '0')}</span>
        <strong>{m.title}</strong>
        {i === 0 && <span className="chosen">✓ Gekozen</span>}
        <span className="tc when">{m.when} · {m.secs}</span>
        <span className="why">{m.why}</span>
      </div>
    ))}
    <figcaption>Zo komt een dienst terug</figcaption>
  </figure>
)

/** The end screen, filling itself in while they type. */
const EndScreen = ({ name, times, insta }: { name: string; times: string; insta: string }) => (
  <figure className="mock outro">
    <div className="outro-card">
      <span className="mark" aria-hidden="true" />
      <strong>{name.trim() || 'Jullie kerk'}</strong>
      <span className="times">{times.trim() || 'Zondag 10:00'}</span>
      <span className="insta">{insta.trim() || '@jullie_kerk'}</span>
    </div>
    <figcaption>Zo sluit elke video af</figcaption>
  </figure>
)

/**
 * Before the number is in, the panel shows where to find it: the address bar of their own
 * browser, with the part they are after lit up. Showing four made-up services instead
 * would be pretending to know something about a church nobody has named yet.
 *
 * Once it checks out, the same panel swaps to their real services.
 */
const Services = ({ found }: { found: { name: string; services: StationService[] } | null }) => {
  if (!found) {
    return (
      <figure className="mock hunting">
        <div className="browser">
          <span className="dots" aria-hidden="true"><i /><i /><i /></span>
          <span className="url">
            kerkdienstgemist.nl/stations/<mark>1341</mark>/events
          </span>
        </div>
        <figcaption>Dit nummer staat in de adresbalk van jullie eigen pagina</figcaption>
      </figure>
    )
  }
  return (
    <figure className="mock lineup">
      <strong className="head">{found.name}</strong>
      {(found.services.length
        ? found.services.slice(0, 4)
        : []
      ).map((s) => (
        <div key={s.id} className="row">
          <span className="when">{s.when}</span>
          <span className="title">{s.title}</span>
        </div>
      ))}
      {found.services.length === 0 && <p className="none">Er staan nu geen diensten op.</p>}
      <figcaption>{found.services.length ? 'Klaar om op te halen' : 'Gevonden, alleen nog leeg'}</figcaption>
    </figure>
  )
}

/**
 * The first five minutes, for whoever does the socials at a church.
 *
 * They open this on a Monday. They did not install it, they cannot open a terminal, and an
 * empty upload box tells them nothing. So it says what it is in their own terms, asks the
 * three things it cannot work without, and checks each answer straight away.
 *
 * The screen is split across the whole window: the question on the left, and on the right
 * a dark panel showing what that answer is going to get them. It fills in while they type,
 * so the name they enter is already standing on the end screen before they press anything,
 * and the number they look up brings back their own services.
 *
 * Nothing is a dead end. The church can be typed by hand, kerkdienstgemist can be skipped,
 * and every answer stays editable later under Merk instellen.
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

  /** Look it up before saving, so a wrong number says so here and not next Sunday. */
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

  const beside = {
    why: <Playing />,
    key: <Moments />,
    church: <EndScreen name={name} times={times} insta={insta} />,
    station: <Services found={found} />,
    ready: <Playing />,
  }[step]

  return (
    <div className="welcome">
      <div className="asking">
        <div className="where">
          <span>{LABEL[step]}</span>
          <span className="rail" aria-hidden="true">
            <span style={{ width: `${(at / (ORDER.length - 1)) * 100}%` }} />
          </span>
          <span className="tc">{at + 1}/{ORDER.length}</span>
        </div>

        <div className="asked">
          {step === 'why' && (
            <>
              <h1>Er moet weer iets online van zondag</h1>
              <p className="lead">
                Je weet meestal wel welk stuk je zoekt. Het terugvinden is het werk, en daarna moet
                het nog geknipt en ondertiteld worden. Preekstof neemt dat over. Jij luistert na en
                zegt wat eruit mag.
              </p>
              <p className="aside">
                De opname blijft op deze computer staan. Alleen de uitgeschreven tekst gaat naar
                Claude, om de goede stukken te vinden.
              </p>
              <div className="acts">
                <button className="primary" onClick={() => go('key')}>Aan de slag</button>
                <span className="soft">Kost je een paar minuten</span>
              </div>
            </>
          )}

          {step === 'key' && (
            <>
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
            </>
          )}

          {step === 'church' && (
            <>
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
            </>
          )}

          {step === 'station' && (
            <>
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
              <div className="acts">
                <button className="primary" disabled={busy || !found} onClick={saveStation}>
                  Ja, dat is ons
                </button>
                <button className="quiet" disabled={busy} onClick={() => finish(true)}>
                  Wij staan daar niet op
                </button>
              </div>
            </>
          )}

          {step === 'ready' && (
            <>
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
            </>
          )}

          {error && <div className="error welcome-error">{error}</div>}
        </div>

        <p className="foot">
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

      <div className="showing">{beside}</div>
    </div>
  )
}
