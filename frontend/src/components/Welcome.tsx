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
 * The first five minutes, for a church nobody here can see.
 *
 * Someone opens this app for the first time on a Monday morning. They did not install it,
 * they cannot open a terminal, and if the first thing they meet is an empty upload box they
 * will close the window again. So the app explains itself, asks the three things it cannot
 * work without, and checks each answer on the spot rather than twenty minutes later.
 *
 * Nothing here is a dead end. The church can be typed by hand, kerkdienstgemist can be
 * skipped outright, and everything asked here stays editable under Merk instellen.
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
      const station_ = await serviceApi.station(id)
      setFound({ name: station_.name, services: station_.services })
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
      <ol className="welcome-steps" aria-label="Stappen">
        {ORDER.map((s, i) => (
          <li key={s} className={i === at ? 'now' : i < at ? 'past' : ''}>
            <span className="dot">{i < at ? '✓' : i + 1}</span>
            <span>{LABEL[s]}</span>
          </li>
        ))}
      </ol>

      <section className="card welcome-card">
        {step === 'why' && (
          <>
            <h1>Van een hele dienst naar een clip die iemand afkijkt</h1>
            <p className="lead">
              Preekstof luistert de opname van jullie dienst uit, leest de preek door en stelt de
              momenten voor die als losse video werken. Jij luistert ze na en kiest. Wat je kiest
              wordt geknipt, ondertiteld, op de spreker gezet en afgemaakt met jullie eindscherm.
            </p>
            <div className="why">
              <div>
                <strong>Een uur werk wordt een kwartier</strong>
                <span>Geen tijdcodes opschrijven, geen ondertitels typen, geen bijsnijden per clip.</span>
              </div>
              <div>
                <strong>De opname blijft hier</strong>
                <span>Video en geluid verlaten deze computer nooit. Alleen de uitgeschreven tekst gaat naar Claude om de momenten te zoeken.</span>
              </div>
              <div>
                <strong>Jij houdt het laatste woord</strong>
                <span>Elk voorstel kun je beluisteren, bijstellen of weggooien, en je kunt zelf een fragment uit de tekst knippen.</span>
              </div>
            </div>
            <p className="hint">
              Drie dingen zijn nog nodig. Het duurt een paar minuten en je doet het één keer.
            </p>
            <div className="acts">
              <button className="primary" onClick={() => go('key')}>Aan de slag</button>
            </div>
          </>
        )}

        {step === 'key' && (
          <>
            <h1>Een sleutel voor Claude</h1>
            <p className="lead">
              Het doorlezen van de preek gebeurt door Claude. Daar heeft de kerk een eigen sleutel
              voor nodig, en die betaal je per dienst: rond de <strong>€ 0,03</strong> voor een
              dienst van een uur. Uitschrijven, knippen en ondertitelen kost niets en gebeurt hier.
            </p>
            <ol className="doing">
              <li>Maak een account op <a href="https://console.anthropic.com/" target="_blank" rel="noreferrer">console.anthropic.com</a> en zet er wat tegoed op.</li>
              <li>Ga naar <strong>API keys</strong> en maak een nieuwe sleutel.</li>
              <li>Plak hem hieronder. Hij wordt meteen uitgeprobeerd en daarna hier op de computer bewaard.</li>
            </ol>
            <label htmlFor="key">Sleutel</label>
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
            {now.hasKey && !error && <p className="good">Er staat al een werkende sleutel klaar.</p>}
            <div className="acts">
              <button className="primary" disabled={busy || !key.trim()} onClick={saveKey}>
                {busy ? 'Even proberen…' : 'Bewaren en uitproberen'}
              </button>
              {now.hasKey && <button onClick={() => go('church')}>Deze houden</button>}
              <button className="bare small" onClick={() => go('church')}>Later doen</button>
            </div>
            <p className="hint">
              Liever helemaal niets naar buiten? Dan kan het ook met een model op deze computer:
              zet <code>LLM_PROVIDER=ollama</code> in config.env.
            </p>
          </>
        )}

        {step === 'church' && (
          <>
            <h1>Van welke kerk is dit?</h1>
            <p className="lead">
              Deze naam komt op het eindscherm achter elke video, samen met de diensttijden en het
              Instagram-account. Je kunt het later allemaal aanpassen onder <strong>Merk instellen</strong>.
            </p>
            <div className="fields wide-labels">
              <label htmlFor="cname">Naam kerk</label>
              <input id="cname" value={name} placeholder="Nieuwe Kerk Utrecht"
                     onChange={(e) => setName(e.target.value)} />
              <label htmlFor="ctimes">Diensttijden</label>
              <input id="ctimes" value={times} placeholder="10:00 Wittevrouwen, 11:30 Wilhelminapark"
                     onChange={(e) => setTimes(e.target.value)} />
              <p className="hint span">Scheid meerdere tijden met een komma. Niet verplicht.</p>
              <label htmlFor="cinsta">Instagram</label>
              <input id="cinsta" value={insta} placeholder="@nieuwekerk_utrecht"
                     onChange={(e) => setInsta(e.target.value)} />
            </div>
            <div className="acts">
              <button className="primary" disabled={busy || !name.trim()} onClick={saveChurch}>Verder</button>
              <button className="bare small" onClick={() => go('key')}>Terug</button>
            </div>
          </>
        )}

        {step === 'station' && (
          <>
            <h1>Staan jullie diensten op Kerkdienstgemist?</h1>
            <p className="lead">
              Dan haalt de app de opname zelf op en hoef je niets te uploaden. Ga naar jullie eigen
              pagina op kerkdienstgemist.nl en kijk in de adresbalk: achter <code>/stations/</code>
              staat een nummer. Dat is het.
            </p>
            <p className="sample tc">https://kerkdienstgemist.nl/stations/<strong>1341</strong>/events</p>
            <div className="row">
              <input
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
              <div className="good found-station">
                <strong>{found.name}</strong>
                {found.services.length > 0 ? (
                  <span>
                    {found.services.length} diensten staan klaar, de laatste is{' '}
                    <em>{found.services[0].title}</em>.
                  </span>
                ) : (
                  <span>Gevonden, maar er staan nu geen diensten op.</span>
                )}
              </div>
            )}
            <div className="acts">
              <button className="primary" disabled={busy || !found} onClick={saveStation}>
                Dit is onze kerk
              </button>
              <button className="bare small" disabled={busy} onClick={() => finish(true)}>
                Wij gebruiken dit niet, ik upload zelf
              </button>
            </div>
          </>
        )}

        {step === 'ready' && (
          <>
            <h1>Klaar om te beginnen</h1>
            <p className="lead">
              {now.churchName ? `${now.churchName} staat ingesteld. ` : ''}
              Sleep de opname van een dienst naar binnen, of kies er een uit de lijst als jullie op
              Kerkdienstgemist staan. De app schrijft hem uit, en ondertussen kun je de tekst al
              doorlezen en zelf een fragment uitknippen.
            </p>
            <ul className="next">
              <li>Uitschrijven duurt een tijdje en gebeurt op deze computer. Laat het venster openstaan.</li>
              <li>Het zoeken naar momenten duurt ongeveer een minuut en kost een paar cent.</li>
              <li>Het eindscherm, de ondertitelstijl en de woordenlijst staan onder <strong>Merk instellen</strong>.</li>
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
          </>
        )}

        {error && <div className="error" style={{ marginTop: '1rem', marginBottom: 0 }}>{error}</div>}
      </section>

      <p className="welcome-foot">
        Preekstof {now.version}
        {step !== 'ready' && (
          <>
            {' · '}
            <button className="bare small" onClick={() => finish(now.skippedStation)}>
              Overslaan en zelf instellen
            </button>
          </>
        )}
      </p>
    </div>
  )
}
