import { useEffect, useRef, useState } from 'react'
import { ApiError, serviceApi, type ClipCandidate, type Service, type ServiceSummary } from '../api'
import { useChurch } from '../church'
import { forget, remember, remembered } from '../remember'
import { formatTime } from '../subtitleLayout'
import ClipSuggestions from './ClipSuggestions'
import Section from './Section'
import ServiceTimeline from './ServiceTimeline'
import ServiceTranscript from './ServiceTranscript'
import StationServices from './StationServices'
import Report from './Report'
import Still from './Still'
import Steps from './Steps'

const STORAGE_KEY = 'service'
const BUSY = new Set(['fetching', 'transcribing', 'analyzing', 'processing'])
const STEPS = ['Opname binnenhalen', 'Uitschrijven', 'Momenten zoeken', 'Fragmenten kiezen', 'Clips maken']

const STATUS_LABEL: Record<Service['status'], string> = {
  created: 'Wacht op een opname',
  fetching: 'Opname wordt opgehaald',
  uploaded: 'Opname ontvangen',
  transcribing: 'Dienst wordt uitgeschreven',
  transcribed: 'Uitgeschreven',
  analyzing: 'Beste momenten worden gezocht',
  ready: 'Suggesties staan klaar',
  processing: 'Clips worden gemaakt',
  complete: 'Klaar',
  error: 'Er ging iets mis',
}

const STATUS_TEXT: Record<Service['status'], string> = {
  created: 'Plak hierboven de link naar de dienst, of sleep het bestand naar binnen.',
  fetching: 'De opname wordt binnengehaald van het adres dat je gaf. Hoe lang dat duurt hangt af van je verbinding.',
  uploaded: 'De opname is binnen. Klik op Uitschrijven om de gesproken tekst om te zetten in tekst.',
  transcribing:
    'De dienst wordt snel doorgeluisterd, genoeg om de momenten te kunnen vinden. Laat dit venster open staan; de balk hieronder laat de voortgang zien.',
  transcribed: 'De tekst is klaar, nog wat ruw. Lees hem hieronder door en knip er zelf een fragment uit, of laat de computer de beste momenten zoeken. Wat je kiest wordt straks woord voor woord opnieuw uitgeschreven.',
  analyzing: 'De dienst wordt doorgelezen op momenten die als losse video werken. Lees zelf vast mee hieronder: wat je nu uitknipt blijft staan als het zoeken klaar is.',
  ready:
    'Hieronder staan de fragmenten, de beste bovenaan, met wat je zelf knipte erboven. Beluister ze, vink aan wat je wilt gebruiken en pas zo nodig het begin en einde aan. Klik daarna onderaan op Gekozen fragmenten verwerken.',
  processing: 'De gekozen fragmenten worden uit de opname geknipt, netjes uitgeschreven en op de spreker gezet. Dit duurt ongeveer een halve minuut per fragment.',
  complete: 'De clips staan klaar bij Gemaakte clips. Open een clip om de ondertitels na te kijken, het beeldkader te kiezen en de video te maken.',
  error: 'Probeer de laatste stap opnieuw. Blijft het misgaan, geef de melding hieronder dan door aan degene die de app beheert.',
}

const STEP_FOR_STATUS: Record<Service['status'], number> = {
  created: 0, fetching: 0, uploaded: 1, transcribing: 1, transcribed: 2, analyzing: 2, ready: 3, processing: 4, complete: 5, error: 0,
}

interface Props {
  onOpenClip: (projectId: string) => void
}

/** Full-service entry point: upload -> transcribe -> analyze -> review candidates -> process. */
/** Says what the search sends to Claude and what it costs, before the user spends anything. */
function CostNote({ analysis }: { analysis: NonNullable<Service['analysis']> }) {
  if (analysis.provider === 'ollama') {
    return (
      <p className="cost">
        Bij <strong>Beste momenten zoeken</strong> gaat de uitgeschreven tekst naar het model op deze computer
        ({analysis.model}). Dat kost niets en er gaat niets naar buiten.
      </p>
    )
  }
  // A sermon almost always fits in one call. Saying so is the difference between a volunteer
  // who waits a minute and one who wonders whether the app has hung.
  const pieces = analysis.windows === 1 ? 'in \u00e9\u00e9n keer' : `in ${analysis.windows} stukken`
  return (
    <p className="cost">
      Bij <strong>Beste momenten zoeken</strong> gaat alleen de uitgeschreven tekst naar Claude, {pieces}
      {analysis.skippedMinutes > 0 && (
        <> · {analysis.skippedMinutes} minuten zang en afkondigingen blijven thuis</>
      )}. Dat kost tokens: ongeveer <strong>{analysis.tokens.toLocaleString('nl-NL')} tokens</strong>, dus rond de{' '}
      <strong>€ {analysis.costEur.toFixed(2).replace('.', ',')}</strong> met {analysis.model}. De video en het geluid blijven
      op deze computer.
      <Privacy />
    </p>
  )
}

/**
 * The short version, where somebody is already reading about what goes out.
 *
 * Folded shut on purpose. A volunteer cutting a clip does not need this every Sunday, and a
 * church council deciding whether to allow the app at all needs more than four sentences,
 * which is what the link is for. What it must not be is absent: the honest answer here is a
 * good one, and it is only a weakness while nobody has written it down.
 */
const Privacy = () => (
  <details className="privacy">
    <summary>Wat gaat er precies naar buiten?</summary>
    <p>
      Alleen de uitgeschreven tekst van de preek, naar Anthropic, met jullie eigen sleutel.
      Nooit beeld of geluid. Onder de zakelijke voorwaarden van de API wordt die tekst niet
      gebruikt om modellen te trainen. Naar de maker van deze app gaat niets; er zit geen
      telemetrie in.
    </p>
    <p>
      Let op wat er in zo&apos;n tekst kan staan. Noemt de voorganger tijdens de preek de naam
      van iemand die ziek is, dan gaat die naam mee. Wil de kerk dat niet, dan houdt{' '}
      <code>LLM_PROVIDER=ollama</code> in <code>config.env</code> alles binnen het gebouw.
    </p>
    <p>
      <a href="/privacy" target="_blank" rel="noreferrer">De hele pagina, om aan de kerkenraad te geven ↗</a>
    </p>
  </details>
)

export default function ServiceView({ onOpenClip }: Props) {
  const [service, setService] = useState<Service | null>(null)
  const [uploading, setUploading] = useState<number | null>(null)
  // Most churches already publish the service somewhere, so the link is the shorter way
  // in. A church that told the welcome it does not opens on the file tab instead.
  const [how, setHow] = useState<'link' | 'file'>('link')
  const picked = useRef(false)
  const [link, setLink] = useState('')
  const [earlier, setEarlier] = useState<ServiceSummary[]>([])
  const church = useChurch()
  const [offline, setOffline] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const autoChain = useRef(false)
  const dirty = useRef(false)
  // One player for the whole page: reading the transcript and listening to a fragment are
  // the same seat, and two <video> elements on one recording is one too many.
  const videoRef = useRef<HTMLVideoElement>(null)
  const [playing, setPlaying] = useState<string | null>(null)
  const [time, setTime] = useState(0)
  const [tab, setTab] = useState<'moments' | 'text'>('text')

  const fail = (e: unknown) => {
    if (e instanceof ApiError && e.offline) {
      setOffline(true)
      return
    }
    setOffline(false)
    setError(e instanceof Error ? e.message : String(e))
  }

  const adopt = (s: Service) => {
    setService(s)
    remember(STORAGE_KEY, s.id)
  }

  // Restore the last service after a reload.
  useEffect(() => {
    const saved = remembered(STORAGE_KEY)
    if (!saved) return
    serviceApi.get(saved).then(setService).catch(() => forget(STORAGE_KEY))
  }, [])

  // What is there to go back to. Asked again whenever you are between services, so one you
  // just put away shows up in the list right below.
  useEffect(() => {
    if (service?.sourceVideo) return
    let alive = true
    serviceApi.recent().then((list) => alive && setEarlier(list)).catch(() => alive && setEarlier([]))
    return () => {
      alive = false
    }
  }, [service?.sourceVideo, service?.id])

  // Poll while a job runs; chain transcribe -> analyze automatically after an upload.
  useEffect(() => {
    if (!service) return
    if (BUSY.has(service.status)) {
      // A few missed polls are a hiccup, not a failure: the work carries on in the app itself.
      let misses = 0
      const handle = setInterval(() => {
        serviceApi
          .status(service.id)
          .then((s) => {
            misses = 0
            setOffline(false)
            // While a job runs the small payload is enough; when it is over, load everything once.
            if (BUSY.has(s.status)) {
              setService((prev) => (prev ? { ...prev, status: s.status, error: s.error, warning: s.warning, job: s.job } : prev))
            } else {
              serviceApi.get(service.id).then(setService).catch(fail)
            }
          })
          .catch((e) => {
            misses += 1
            if (misses >= 3) fail(e)
          })
      }, 2000)
      return () => clearInterval(handle)
    }
    if (autoChain.current && service.status === 'uploaded') {
      serviceApi.transcribe(service.id).then(setService).catch(fail)
    } else if (autoChain.current && service.status === 'transcribed') {
      autoChain.current = false
      serviceApi.analyze(service.id).then(setService).catch(fail)
    }
  }, [service])

  // Which side you land on when a service opens: the fragments when there already are
  // some, the text when there are not. After that the tabs only move when you click one.
  // Being pulled away mid-selection because the search happened to finish is no help.
  useEffect(() => {
    setTab(service && service.candidates.length > 0 ? 'moments' : 'text')
    setPlaying(null)
    setTime(0)
  }, [service?.id])

  const preview = (cand: ClipCandidate) => {
    const v = videoRef.current
    if (!v) return
    if (playing === cand.id && !v.paused) {
      v.pause()
      return
    }
    setPlaying(cand.id)
    v.currentTime = cand.start
    void v.play().catch(() => undefined)
  }

  /** From the timeline: play it, and put the card it belongs to in front of you. */
  const jump = (cand: ClipCandidate) => {
    setTab('moments')
    preview(cand)
    requestAnimationFrame(() =>
      document.getElementById(`f-${cand.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }

  /**
   * A fragment somebody cut out of the transcript. Saved straight away rather than on the
   * usual debounce: it is a deliberate act, and the answer carries both the name the server
   * gave it and anything the search turned up while this was in flight.
   */
  const cut = async (candidate: ClipCandidate) => {
    if (!service) return
    const own = service.candidates.filter((c) => c.source === 'self')
    const found = service.candidates.filter((c) => c.source !== 'self')
    const wanted = [...own, candidate, ...found]
    setService({ ...service, candidates: wanted })
    dirty.current = false
    try {
      const saved = await serviceApi.saveCandidates(service.id, wanted)
      setService((prev) => (prev ? { ...prev, candidates: saved } : prev))
    } catch (e) {
      fail(e)
    }
  }

  useEffect(() => {
    if (picked.current || church === null) return
    if (!church.kerkdienstgemistStation.trim()) setHow('file')
  }, [church])

  const upload = async (file: File) => {
    setError(null)
    setUploading(0)
    try {
      const s = service && !service.sourceVideo ? service : await serviceApi.create()
      autoChain.current = true
      adopt(await serviceApi.upload(s.id, file, setUploading))
    } catch (e) {
      fail(e)
      autoChain.current = false
    } finally {
      setUploading(null)
    }
  }

  const fetchFrom = async (url: string) => {
    if (!url.trim()) return
    setError(null)
    try {
      const s = service && !service.sourceVideo ? service : await serviceApi.create()
      autoChain.current = true
      adopt(await serviceApi.link(s.id, url.trim()))
      setLink('')
    } catch (e) {
      fail(e)
      autoChain.current = false
    }
  }

  /**
   * Put the current service away so another can be picked. Nothing is deleted: it comes
   * back under "Eerder mee gewerkt". Work that is still running is stopped first, because
   * waiting out a half-minute stop and then pressing this again is two steps too many.
   */
  const pickAnother = async () => {
    if (service && BUSY.has(service.status)) {
      if (!window.confirm(`"${service.title}" is nog bezig. Stoppen en een andere dienst kiezen?`)) return
      try {
        await serviceApi.stop(service.id)
      } catch (e) {
        fail(e)  // it kept running, so leave it in view rather than pretend otherwise
        return
      }
    }
    setService(null)
    setError(null)
    setLink('')
    autoChain.current = false
    dirty.current = false
    forget(STORAGE_KEY)
  }

  const openEarlier = (id: string) => {
    setError(null)
    serviceApi.get(id).then(adopt).catch(fail)
  }

  const run = (action: (id: string) => Promise<Service>) => {
    if (!service) return
    setError(null)
    action(service.id).then(setService).catch(fail)
  }

  // Candidate edits (selection, boundaries) are saved with a short debounce.
  const changeCandidates = (candidates: ClipCandidate[]) => {
    if (!service) return
    dirty.current = true
    setService({ ...service, candidates })
  }
  useEffect(() => {
    if (!service || !dirty.current) return
    const handle = setTimeout(() => {
      dirty.current = false
      setSaving(true)
      serviceApi
        .saveCandidates(service.id, service.candidates)
        // The search can land while this is in flight. The answer already has both lists in
        // it, so take that rather than the half of it this browser knew about.
        .then((saved) => setService((prev) =>
          prev && saved.length !== prev.candidates.length ? { ...prev, candidates: saved } : prev))
        .catch(fail)
        .finally(() => setSaving(false))
    }, 500)
    return () => clearTimeout(handle)
  }, [service])

  const processSelected = async () => {
    if (!service) return
    setError(null)
    try {
      await serviceApi.saveCandidates(service.id, service.candidates)
      dirty.current = false
      setService(await serviceApi.processSelected(service.id))
    } catch (e) {
      fail(e)
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) void upload(file)
  }

  const busy = service ? BUSY.has(service.status) : false
  // Only making the clips actually locks the list: it walks the fragments as it goes, so
  // changing them underneath would lose one. While the search runs, cutting your own is
  // the whole point of those minutes.
  const locked = service?.status === 'processing'
  const hasVideo = Boolean(service?.sourceVideo && service.sourceInfo)
  const selectedCount = service?.candidates.filter((c) => c.selected).length ?? 0
  const chosen = service?.candidates.filter((c) => c.shortlisted) ?? []
  const extra = service?.candidates.filter((c) => !c.shortlisted) ?? []
  const nowPlaying = service?.candidates.find((c) => c.id === playing)
  const sentences = service?.transcriptData?.segments.length ?? 0
  const progress = service?.job ? Math.round(service.job.progress * 100) : null
  const stopping = Boolean(service?.job?.message?.startsWith('Bezig met stoppen'))
  // While a recording is being fetched there is nothing to choose; the card below says what
  // is happening. Once one is in, the drop zone stays as the way to start over.
  const showSource = hasVideo || !busy

  return (
    <div>
      <header className="page-head">
        <h1>Hele dienst</h1>
        <p>Geef de link naar de dienst, of upload het bestand. De computer schrijft de dienst uit en zoekt de momenten die als korte video werken. Jij luistert ze na en kiest.</p>
      </header>

      <Steps steps={STEPS} current={service && hasVideo ? STEP_FOR_STATUS[service.status] : 0} />

      {offline && <div className="offline">Geen verbinding met de app. Staat het zwarte venster nog open? Het werk gaat daar gewoon door; zodra de verbinding terug is, zie je de voortgang weer.</div>}
      {error && (
        <div className="error">
          {error}
          <Report trouble={error} service={service?.id} small />
        </div>
      )}

      {showSource && !hasVideo && uploading === null && (
        <div className="seg source-pick">
          <button className={how === 'link' ? 'on' : ''} onClick={() => { picked.current = true; setHow('link') }}>Link naar de dienst</button>
          <button className={how === 'file' ? 'on' : ''} onClick={() => { picked.current = true; setHow('file') }}>Bestand van deze computer</button>
        </div>
      )}

      {!showSource ? null : how === 'link' && !hasVideo && uploading === null ? (
        <>
        <StationServices
          key={church?.kerkdienstgemistStation ?? ''}
          station={church?.kerkdienstgemistStation ?? ''}
          disabled={busy}
          onPick={fetchFrom}
        />
        <div className="paste">
          <label htmlFor="link"><strong>Of plak het adres van een dienst</strong></label>
          <div className="row">
            <input
              id="link"
              type="url"
              value={link}
              disabled={busy}
              placeholder="https://kerkdienstgemist.nl/stations/…/events/recording/…"
              onChange={(e) => setLink(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchFrom(link)}
            />
            <button className="primary" disabled={busy || !link.trim()} onClick={() => fetchFrom(link)}>Ophalen</button>
          </div>
          <p className="hint">
            Kerkdienstgemist, YouTube, Vimeo, Facebook of een directe link naar een mp4. Bij
            Kerkdienstgemist plak je gewoon het adres van de dienst zoals het in je adresbalk
            staat. Lukt het met een andere site niet, download de opname daar dan en gebruik het
            tabblad hiernaast.
          </p>
        </div>
        </>
      ) : (
        <div className={hasVideo ? 'open-service' : ''}>
          <label
            className={`drop ${dragging ? 'active' : ''} ${hasVideo ? 'compact' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragging(true)
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input type="file" accept="video/*,.mp4,.mov,.m4v,.mkv,.webm" disabled={uploading !== null || busy} onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            {uploading !== null ? (
              <span className="uploading">
                <strong>Bezig met uploaden…</strong>
                <span className="bar"><span style={{ display: 'block', height: '100%', background: 'var(--purple)', width: `${Math.round(uploading * 100)}%` }} /></span>
                <span className="meta">{Math.round(uploading * 100)}%</span>
              </span>
            ) : hasVideo ? (
              <span className="meta">Sleep hier een andere opname, of klik om een bestand te kiezen.</span>
            ) : (
              <>
                <strong>Sleep hier de opname van de hele dienst, of klik om een bestand te kiezen</strong>
                <span className="hint">Daarna loopt het vanzelf door: uitschrijven, en dan zoeken naar bruikbare momenten.</span>
              </>
            )}
          </label>
          {/* The button sits outside the label, or clicking it would open the file chooser. */}
          {hasVideo && (
            <button
              className="small"
              title="Deze dienst blijft bewaard; je kunt hem hieronder weer openen"
              onClick={pickAnother}
            >
              Andere dienst kiezen
            </button>
          )}
        </div>
      )}

      {showSource && !hasVideo && uploading === null && (
        <Earlier services={earlier} disabled={busy} onOpen={openEarlier} />
      )}

      {service && (hasVideo || service.status === 'fetching' || service.status === 'error') && (
        <>
          <section className="card">
            <header className="service-head">
              {hasVideo && service.posterUrl && <Still src={service.posterUrl} />}
              <div>
                <h2>{hasVideo ? service.title : service.status === 'error' ? 'Deze link werkte niet' : STATUS_LABEL[service.status]}</h2>
                {hasVideo && service.preacher && <span className="preacher">{service.preacher}</span>}
                {hasVideo && (
                  <span className="meta">{formatTime(service.sourceInfo!.duration)} · {service.sourceInfo!.width}×{service.sourceInfo!.height}</span>
                )}
              </div>
              {/* Without a recording the heading already says the state; twice is once too many. */}
              {hasVideo && (
                <div className={`state ${service.status === 'ready' || service.status === 'complete' ? 'ok' : ''} ${service.status === 'error' ? 'bad' : ''}`}>
                  {busy && <span className="spinner" />}
                  {STATUS_LABEL[service.status]}
                  {saving ? ' · opslaan' : ''}
                </div>
              )}
            </header>
            {/* Without a recording the failure is the link's, and its own message says more
                than the general "try the last step again" would. */}
            {(hasVideo || service.status !== 'error') && <p className="say">{STATUS_TEXT[service.status]}</p>}
            {service.status === 'error' && (
              <div className="error" style={{ marginTop: '0.8rem', marginBottom: 0 }}>
                {service.error}
                <Report trouble={service.error ?? ''} service={service.id} small />
              </div>
            )}
            {service.warning && <div className="warning">{service.warning}</div>}
            {busy && stopping && <p className="hint">Stoppen kan een halve minuut duren; de app maakt het huidige stukje eerst af.</p>}
            {/* Making the clips reports in the dock, which is on screen wherever you have
                scrolled to; two bars saying the same thing is one too many. */}
            {busy && service.status !== 'processing' && (
              <div className={`progress ${progress ? 'busy' : 'waiting'}`}>
                <div className="bar"><div style={{ width: `${progress ?? 0}%` }} /></div>
                <div className="label">
                  <span>{service.job?.message ?? STATUS_LABEL[service.status]}</span>
                  <span>
                    {progress ? `${progress}%` : ''}
                    <button
                      className="bare small"
                      style={{ marginLeft: '0.6rem' }}
                      disabled={stopping}
                      onClick={() => run(serviceApi.stop)}
                    >
                      {stopping ? 'Stoppen…' : 'Stoppen'}
                    </button>
                  </span>
                </div>
              </div>
            )}
            {!busy && hasVideo && !service.transcript && (
              <div className="fields about">
                <label htmlFor="sermonTitle">Waar gaat het over?</label>
                <input
                  id="sermonTitle"
                  defaultValue={service.sermonTitle}
                  placeholder="Rust in een druk leven"
                  onBlur={(e) => serviceApi.setAbout(service.id, e.target.value, service.series).then(setService).catch(fail)}
                />
                <label htmlFor="sermonSeries">Serie</label>
                <input
                  id="sermonSeries"
                  defaultValue={service.series}
                  placeholder="Onderweg"
                  onBlur={(e) => serviceApi.setAbout(service.id, service.sermonTitle, e.target.value).then(setService).catch(fail)}
                />
                <p className="hint span">
                  Niet verplicht. Als je het invult weet de computer waar hij op moet letten bij het uitschrijven
                  en bij het kiezen van momenten.
                </p>
              </div>
            )}
            {!busy && hasVideo && (
              <label className="choice">
                <input
                  type="checkbox"
                  checked={service.accurate}
                  onChange={(e) => serviceApi.setAccuracy(service.id, e.target.checked).then(setService).catch(fail)}
                />
                <span>
                  <strong>Nauwkeuriger uitschrijven</strong>
                  <span className="meta"> · het grotere model hoort namen en moeilijke woorden beter. Het luistert alleen naar de fragmenten die je kiest, dus het kost seconden en niet het uur dat het over de hele dienst zou kosten.</span>
                </span>
              </label>
            )}
            {!busy && hasVideo && (
              <div className="acts" style={{ marginTop: '1rem' }}>
                {!service.transcript && <button className="primary" onClick={() => run(serviceApi.transcribe)}>Uitschrijven</button>}
                {service.transcript && service.candidates.length === 0 && (
                  <button className="primary" onClick={() => run(serviceApi.analyze)}>Beste momenten zoeken</button>
                )}
                {service.transcript && service.candidates.length > 0 && (
                  <button onClick={() => run(serviceApi.analyze)}>Opnieuw zoeken</button>
                )}
                {service.transcript && <button onClick={() => run(serviceApi.transcribe)}>Opnieuw uitschrijven</button>}
              </div>
            )}
            {!busy && service.transcript && service.analysis && <CostNote analysis={service.analysis} />}
          </section>

          {service.transcript && (
            <Section
              title="De dienst"
              intro="Luister mee, lees de hele tekst door en knip eruit wat je wilt gebruiken. De balk laat zien waar elk fragment zit en hoe de dienst is opgebouwd."
              aside={service.candidates.length > 0
                ? <span className="meta">{chosen.length} gekozen{extra.length > 0 ? ` · ${extra.length} ook gevonden` : ''}</span>
                : undefined}
            >
              <ServiceTimeline service={service} time={time} playing={playing} onPick={jump} />

              <div className="player">
                <video
                  ref={videoRef}
                  src={serviceApi.sourceUrl(service.id)}
                  preload="metadata"
                  playsInline
                  controls
                  onTimeUpdate={(e) => {
                    const v = e.currentTarget
                    setTime(v.currentTime)
                    const cand = service.candidates.find((c) => c.id === playing)
                    if (cand && v.currentTime >= cand.end) {
                      v.pause()
                      v.currentTime = cand.end
                    }
                  }}
                />
                <p className="meta" style={{ marginTop: '0.35rem' }}>
                  {nowPlaying
                    ? `${nowPlaying.title} speelt · stopt om ${formatTime(nowPlaying.end)}`
                    : 'Klik op een balkje hierboven, of op een zin in de tekst.'}
                </p>
              </div>

              <div className="seg tabs">
                <button className={tab === 'moments' ? 'on' : ''} onClick={() => setTab('moments')}>
                  Fragmenten
                  {service.candidates.length > 0 && <span className="count">{service.candidates.length}</span>}
                </button>
                <button className={tab === 'text' ? 'on' : ''} onClick={() => setTab('text')}>
                  Hele tekst
                  <span className="count">{sentences}</span>
                </button>
              </div>

              {tab === 'moments' ? (
                <ClipSuggestions
                  service={service}
                  video={videoRef}
                  playing={playing}
                  disabled={locked}
                  onPreview={preview}
                  onChange={changeCandidates}
                />
              ) : (
                <ServiceTranscript
                  service={service}
                  video={videoRef}
                  time={time}
                  disabled={locked}
                  onCut={cut}
                />
              )}
            </Section>
          )}

          {(service.candidates.length > 0 || service.clips.length > 0) && (
            <div className="dock">
              {service.clips.length > 0 && (
                <div className="ready">
                  <span className="meta">Klaar om te bewerken</span>
                  <div className="chips">
                    {service.clips.map((clip) => (
                      <button
                        key={clip.projectId}
                        className="chip"
                        title={`${clip.title} · ${formatTime(clip.start)} – ${formatTime(clip.end)}`}
                        onClick={() => onOpenClip(clip.projectId)}
                      >
                        {clip.title} →
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {/* Making the clips takes a while now that the speaker is looked for in each
                  of them, and the button that started it is down here, not up in the card. */}
              {service.status === 'processing' ? (
                <div className={`progress dock-busy ${progress ? 'busy' : 'waiting'}`}>
                  <div className="bar"><div style={{ width: `${progress ?? 0}%` }} /></div>
                  <div className="label">
                    <span>{service.job?.message ?? 'Clips worden gemaakt'}</span>
                    <span>
                      {progress ? `${progress}%` : ''}
                      <button
                        className="bare small"
                        style={{ marginLeft: '0.6rem' }}
                        disabled={stopping}
                        onClick={() => run(serviceApi.stop)}
                      >
                        {stopping ? 'Stoppen…' : 'Stoppen'}
                      </button>
                    </span>
                  </div>
                </div>
              ) : service.candidates.length > 0 && (
                <div className="row">
                  <span>
                    {selectedCount === 0 ? 'Nog geen fragment gekozen' : selectedCount === 1 ? '1 fragment gekozen' : `${selectedCount} fragmenten gekozen`}
                    {busy && selectedCount > 0 && <span className="meta"> · wacht tot het zoeken klaar is</span>}
                  </span>
                  <button className="primary" disabled={busy || selectedCount === 0} onClick={processSelected}>
                    Gekozen fragmenten verwerken
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

const SHORT: Partial<Record<Service['status'], string>> = {
  uploaded: 'nog niet uitgeschreven',
  transcribed: 'uitgeschreven',
  ready: 'momenten gevonden',
  complete: 'clips gemaakt',
  error: 'liep vast',
}

/** What a service is worth coming back for, in one line. */
function tells(s: ServiceSummary): string {
  const bits: string[] = []
  if (s.duration) bits.push(`${Math.round(s.duration / 60)} min`)
  if (s.clips > 0) bits.push(`${s.clips} clip${s.clips === 1 ? '' : 's'} gemaakt`)
  else if (s.moments > 0) bits.push(`${s.moments} momenten gevonden`)
  else if (SHORT[s.status]) bits.push(SHORT[s.status]!)
  if (!s.hasFootage) bits.push('opname opgeruimd')
  return bits.join(' · ')
}

/**
 * The services worked on before. Putting one away to start another should not mean losing
 * it: the text cost half an hour and the found moments cost money, so they stay one click
 * away for as long as they are on disk.
 */
function Earlier({ services, disabled, onOpen }: {
  services: ServiceSummary[]
  disabled: boolean
  onOpen: (id: string) => void
}) {
  if (services.length === 0) return null
  return (
    <div className="earlier">
      <p className="meta">Eerder mee gewerkt</p>
      <div className="chips">
        {services.map((s) => (
          <button
            key={s.id}
            className="chip"
            disabled={disabled}
            title={`${s.title} · ${new Date(s.createdAt).toLocaleDateString('nl-NL')}`}
            onClick={() => onOpen(s.id)}
          >
            <Still src={s.poster} />
            <span className="what">
              <strong>{s.title}</strong>
              {s.preacher && <span className="preacher">{s.preacher}</span>}
              <span className="meta">{tells(s)}</span>
            </span>
          </button>
        ))}
      </div>
      <p className="hint">Weggooien doe je bij Ruimte vrijmaken, boven in de balk.</p>
    </div>
  )
}
