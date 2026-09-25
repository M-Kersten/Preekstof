import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type MusicFile, type MusicSettings } from '../api'
import Section from './Section'

interface Props {
  music: MusicSettings
  onChange: (music: MusicSettings) => void
}

// How much of a track a listen plays, and how long it takes to come up and go down again.
// The render starts every track at its first second, so that is where a listen starts too:
// what you hear here is how the music begins under the clip.
const FRAGMENT = 15
const FADE = 1.2

/** "rustige_piano-01.mp3" reads as "rustige piano 01". The file keeps its own name. */
const shown = (file: string) => file.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim() || file

const clock = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`

const PlayIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
    <path d="M3.5 2.2v9.6c0 .5.5.8.9.5l7.4-4.8a.6.6 0 0 0 0-1L4.4 1.7c-.4-.3-.9 0-.9.5Z" fill="currentColor" />
  </svg>
)

const StopIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
    <rect x="3" y="3" width="8" height="8" rx="1.5" fill="currentColor" />
  </svg>
)

/**
 * One track playing a fragment at a time.
 *
 * Choosing music from a list of file names meant choosing blind: the name says what somebody
 * called the file, not whether it sits well under a sermon. A listen fades in and out, so
 * stopping halfway or moving to the next track never ends in a click.
 */
function useListen() {
  const audio = useRef<HTMLAudioElement | null>(null)
  const frame = useRef(0)
  const [playing, setPlaying] = useState<string | null>(null)
  const [share, setShare] = useState(0)
  const [broken, setBroken] = useState<string | null>(null)

  const stop = useCallback(() => {
    cancelAnimationFrame(frame.current)
    audio.current?.pause()
    audio.current = null
    setPlaying(null)
    setShare(0)
  }, [])

  const listen = useCallback((file: string) => {
    const same = audio.current && playing === file
    stop()
    if (same) return
    setBroken(null)
    const track = new Audio(api.musicUrl(file))
    track.volume = 0
    audio.current = track
    setPlaying(file)
    const tick = () => {
      if (audio.current !== track) return
      const length = Math.min(FRAGMENT, Number.isFinite(track.duration) ? track.duration : FRAGMENT)
      const at = track.currentTime
      track.volume = Math.max(0, Math.min(1, at / FADE, (length - at) / FADE))
      setShare(length ? at / length : 0)
      if (at >= length || track.ended) {
        stop()
        return
      }
      frame.current = requestAnimationFrame(tick)
    }
    track.play().then(() => {
      frame.current = requestAnimationFrame(tick)
    }).catch(() => {
      if (audio.current !== track) return
      stop()
      setBroken(file)
    })
  }, [playing, stop])

  // Leaving the clip, or the page, stops the music with it.
  useEffect(() => stop, [stop])

  return { playing, share, broken, listen, stop }
}

/** Optional background music under the clip, with the speech staying on top. */
export default function MusicPanel({ music, onChange }: Props) {
  const [files, setFiles] = useState<MusicFile[]>([])
  const [lengths, setLengths] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { playing, share, broken, listen } = useListen()

  const load = () => api.music().then(setFiles).catch(() => setFiles([]))
  useEffect(() => {
    load()
  }, [])

  // How long each track is, read from the file itself; only the header is fetched.
  // A file the browser cannot read counts as NaN, so it is asked once and not again.
  useEffect(() => {
    const probes = files.map((f) => {
      const probe = new Audio()
      probe.preload = 'metadata'
      const note = (seconds: number) => setLengths((known) => ({ ...known, [f.file]: seconds }))
      probe.onloadedmetadata = () => note(probe.duration)
      probe.onerror = () => note(Number.NaN)
      probe.src = api.musicUrl(f.file)
      return probe
    })
    return () => probes.forEach((probe) => {
      probe.onloadedmetadata = null
      probe.onerror = null
      probe.removeAttribute('src')
    })
  }, [files])

  const add = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      const { file: name } = await api.uploadMusic(file)
      await load()
      onChange({ ...music, file: name })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const choose = (file: string) => onChange({ ...music, file })
  const on = Boolean(music.file)

  return (
    <Section
      step={5}
      title="Muziek"
      intro="Zet er een rustige track onder als je wilt. De stem blijft leidend: zodra er gepraat wordt gaat de muziek automatisch zachter."
    >
      <ul className="music-list" role="radiogroup" aria-label="Muziek onder de clip">
        <li className={`music-track${on ? '' : ' on'}`}>
          <span className="music-play none" aria-hidden="true" />
          <button className="music-pick" role="radio" aria-checked={!on} onClick={() => choose('')}>
            <span className="music-name">Geen muziek</span>
            <span className="meta">Alleen de stem</span>
          </button>
          {!on && <span className="music-chosen">Gekozen</span>}
        </li>
        {files.map((f) => {
          const chosen = music.file === f.file
          const listening = playing === f.file
          const length = lengths[f.file]
          return (
            <li key={f.file} className={`music-track${chosen ? ' on' : ''}${listening ? ' playing' : ''}`}>
              <button
                className="music-play"
                onClick={() => listen(f.file)}
                aria-label={listening ? `Stop ${shown(f.file)}` : `Luister naar ${shown(f.file)}`}
                title={listening ? 'Stoppen' : `Luister naar de eerste ${FRAGMENT} seconden`}
              >
                {listening ? <StopIcon /> : <PlayIcon />}
              </button>
              <button className="music-pick" role="radio" aria-checked={chosen} onClick={() => choose(f.file)}>
                <span className="music-name">{shown(f.file)}</span>
                <span className="meta">
                  {broken === f.file
                    ? 'Dit bestand kan de browser niet afspelen'
                    : [length && Number.isFinite(length) ? clock(length) : '',
                       `${String(f.sizeMb).replace('.', ',')} MB`].filter(Boolean).join(' · ')}
                </span>
              </button>
              {chosen && <span className="music-chosen">Gekozen</span>}
              {listening && (
                <div className="music-progress" aria-hidden="true">
                  <div style={{ width: `${Math.round(share * 100)}%` }} />
                </div>
              )}
            </li>
          )
        })}
        <li className="music-track music-add">
          <label>
            <span className="music-play plus" aria-hidden="true">+</span>
            <span className="music-name">{busy ? 'Bezig met toevoegen…' : 'Eigen muziek toevoegen'}</span>
            <span className="meta">mp3, m4a, wav, aac of ogg</span>
            <input type="file" accept="audio/*,.mp3,.m4a,.wav,.aac,.ogg" disabled={busy}
                   onChange={(e) => e.target.files?.[0] && add(e.target.files[0])} />
          </label>
        </li>
      </ul>

      {on && (
        <div className="fields music-settings">
          <label htmlFor="vol">Volume</label>
          <div className="inline">
            <input id="vol" type="range" min={0.02} max={0.6} step={0.01} value={music.volume} onChange={(e) => onChange({ ...music, volume: Number(e.target.value) })} />
            <output>{Math.round(music.volume * 100)}%</output>
          </div>

          <label htmlFor="duck">Onder de stem</label>
          <div className="inline">
            <input id="duck" type="checkbox" checked={music.duck} onChange={(e) => onChange({ ...music, duck: e.target.checked })} />
            <label htmlFor="duck">Muziek zachter zetten zodra er gesproken wordt</label>
          </div>

          <label htmlFor="fade">Uitfaden</label>
          <div className="inline">
            <input id="fade" type="range" min={0} max={6} step={0.5} value={music.fadeOut} onChange={(e) => onChange({ ...music, fadeOut: Number(e.target.value) })} />
            <output>{String(music.fadeOut).replace('.', ',')} s</output>
          </div>
        </div>
      )}
      {error && <div className="error" style={{ marginTop: '0.7rem', marginBottom: 0 }}>{error}</div>}
      <p className="hint">
        {on
          ? `Met ▶ hoor je de eerste ${FRAGMENT} seconden, zo begint de muziek ook onder je clip. Op het volume en het zachter worden onder de stem hoor je hem pas in de gemaakte video.`
          : 'Gebruik alleen muziek waarvan je de rechten hebt. Instagram en YouTube halen video’s met beschermde muziek weg.'}
      </p>
    </Section>
  )
}
