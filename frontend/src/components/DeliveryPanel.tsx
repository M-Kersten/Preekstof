import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  MAIN_SHAPE,
  type Delivery,
  type Platform,
  type PostState,
  type Project,
  type RenderStatus,
  type ShapeKey,
  type ShapeState,
  type ShareSettings,
} from '../api'
import { cropGeometry, defaultCrop } from '../crop'
import { remember, remembered } from '../remember'
import { cropAt } from '../track'

interface Props {
  project: Project
  renderStatus: RenderStatus
  /** Bumped when a render finishes, so the players ask for the new file. */
  version: number
  /** Start making these shapes; rejects when the render could not be started. */
  onMake: (shapes: ShapeKey[]) => Promise<void>
  onClose: () => void
}

const PLATFORMS: { id: Platform; label: string }[] = [
  { id: 'instagram', label: 'Instagram' },
  { id: 'facebook', label: 'Facebook' },
  { id: 'whatsapp', label: 'WhatsApp' },
]
const PLATFORM_KEY = 'platform'

const isPlatform = (value: string | null): value is Platform => PLATFORMS.some((p) => p.id === value)

/** A small outline of the shape itself, so the three rows can be told apart at a glance. */
function ShapeIcon({ width, height }: { width: number; height: number }) {
  const tall = 22
  const wide = Math.round((tall * width) / height)
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true">
      <rect x={(26 - wide) / 2} y={(26 - tall) / 2} width={wide} height={tall} rx="2.5"
            fill="none" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  )
}

/**
 * What a shape that has not been made yet will show: the clip's own framing, put in a box of
 * that shape. The same geometry the renderer uses, so what is here is what comes out.
 */
function ShapeFrame({ project, shape }: { project: Project; shape: ShapeState }) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const observer = new ResizeObserver(() => setWidth(el.clientWidth))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const info = project.sourceInfo!
  const output = { width: shape.width, height: shape.height, fps: project.output.fps }
  const moment = Math.min(info.duration * 0.3, 3)
  const framing = cropAt(project.crop ?? defaultCrop(info, project.output), project.track,
                         project.cropStrategy === 'tracked', moment)
  const g = cropGeometry(info, output, framing)
  const scale = width / output.width
  return (
    <div className="shape-frame" ref={box}>
      {width > 0 && (
        <video
          src={api.sourceUrl(project.id)}
          muted
          playsInline
          preload="auto"
          onLoadedMetadata={(e) => (e.currentTarget.currentTime = project.sourceStart + moment)}
          style={{
            width: g.scaledW * scale,
            height: g.scaledH * scale,
            left: ((output.width - g.cropW) / 2 - g.left) * scale,
            top: ((output.height - g.cropH) / 2 - g.top) * scale,
          }}
        />
      )}
    </div>
  )
}

/** Put text on the clipboard; the old way for a browser that will not allow the new one. */
async function copyText(text: string, fallback: HTMLTextAreaElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    if (!fallback) return false
    fallback.select()
    return document.execCommand('copy')
  }
}

const dutchMb = (mb: number | null) => (mb === null ? '' : `${mb.toFixed(1).replace('.', ',')} MB`)

/**
 * The step after "Video maken": what the clip can become, and what goes under it.
 *
 * A finished render used to end in a download link, which left the two questions a volunteer
 * actually has at that point unanswered: is this the right shape for where it is going, and
 * what do I write under it. This answers both in one place. The shapes sit on the left of
 * the text because that is the order they are needed in: first the video, then the words.
 *
 * Everything that is set once for the church (which shapes are always made, je or u, the
 * hashtags, the link) can be set right here, where the need for it shows up.
 */
export default function DeliveryPanel({ project, renderStatus, version, onMake, onClose }: Props) {
  const [delivery, setDelivery] = useState<Delivery | null>(null)
  const [chosen, setChosen] = useState<ShapeKey>(MAIN_SHAPE)
  const [making, setMaking] = useState<ShapeKey | null>(null)
  const [queue, setQueue] = useState<ShapeKey[]>([])
  const [post, setPost] = useState<PostState | null>(null)
  const [platform, setPlatform] = useState<Platform>(() => {
    const kept = remembered(PLATFORM_KEY)
    return isPlatform(kept) ? kept : 'instagram'
  })
  const [texts, setTexts] = useState<Record<Platform, string> | null>(null)
  const [copied, setCopied] = useState<Platform | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [hashtags, setHashtags] = useState('')
  const [link, setLink] = useState('')
  const typed = useRef<Partial<Record<Platform, boolean>>>({})
  const area = useRef<HTMLTextAreaElement>(null)
  const askedToWrite = useRef(false)
  const rendering = renderStatus.status === 'running'

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e))

  const adoptShare = (share: ShareSettings) => {
    setHashtags(share.hashtags.join(' '))
    setLink(share.link)
  }

  const loadDelivery = useCallback(() => {
    api.delivery(project.id).then((d) => {
      setDelivery(d)
      adoptShare(d.share)
    }).catch(fail)
  }, [project.id])

  /** Take the texts from the server, except the one somebody is typing in right now. */
  const adoptPost = useCallback((state: PostState) => {
    setPost(state)
    const fresh = state.post?.texts
    if (!fresh) return
    setTexts((before) => {
      if (!before) return fresh
      const next = { ...fresh }
      for (const p of PLATFORMS) if (typed.current[p.id]) next[p.id] = before[p.id]
      return next
    })
  }, [])

  useEffect(() => {
    loadDelivery()
  }, [loadDelivery, version])

  // A render that stops, for whatever reason, ends the wait for the shape it was making. A
  // finished one bumps `version`, which fetches the new state above.
  useEffect(() => {
    if (renderStatus.status === 'running') return
    if (renderStatus.status === 'done' && making) setChosen(making)
    if (renderStatus.status === 'error' && renderStatus.error && making) setError(renderStatus.error)
    setMaking(null)
    // Only the change of status matters here, not every new reading of the same one.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renderStatus.status])

  const start = useCallback((key: ShapeKey) => {
    setMaking(key)
    onMake([key]).catch((e) => {
      setMaking(null)
      fail(e)
    })
  }, [onMake])

  // One at a time: a shape asked for while another is being made waits its turn.
  useEffect(() => {
    if (rendering || making || !queue.length) return
    const [next, ...rest] = queue
    setQueue(rest)
    start(next)
  }, [rendering, making, queue, start])

  // The texts. A clip made before the app wrote them gets them now, once.
  useEffect(() => {
    api.post(project.id).then((state) => {
      adoptPost(state)
      if (!state.post && state.job.status !== 'running' && !askedToWrite.current) {
        askedToWrite.current = true
        api.rewritePost(project.id).then(adoptPost).catch(fail)
      }
    }).catch(fail)
  }, [project.id, adoptPost])

  const writing = post?.job.status === 'running'
  useEffect(() => {
    if (!writing) return
    const handle = setInterval(() => {
      api.post(project.id).then(adoptPost).catch(() => undefined)
    }, 1000)
    return () => clearInterval(handle)
  }, [writing, project.id, adoptPost])

  // What somebody types is kept, a moment after they stop, and at the latest when the window
  // closes: "Klaar" straight after the last word must not lose it.
  const keep = useCallback((current: Record<Platform, string>) => {
    for (const p of PLATFORMS) {
      if (!typed.current[p.id]) continue
      typed.current[p.id] = false
      api.editPost(project.id, p.id, current[p.id]).then(adoptPost).catch(fail)
    }
  }, [project.id, adoptPost])
  const latest = useRef(texts)
  latest.current = texts
  useEffect(() => {
    if (!texts) return
    const handle = setTimeout(() => keep(texts), 700)
    return () => clearTimeout(handle)
  }, [texts, keep])
  useEffect(() => () => {
    if (latest.current) keep(latest.current)
  }, [keep])

  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [onClose])

  const make = (key: ShapeKey) => {
    setError(null)
    setChosen(key)
    if (rendering || making) {
      setQueue((q) => (q.includes(key) ? q : [...q, key]))
      return
    }
    start(key)
  }

  const saveShare = async (patch: Partial<ShareSettings>) => {
    if (!delivery) return
    setError(null)
    try {
      const share = await api.saveShare({ ...delivery.share, ...patch })
      setDelivery({
        ...delivery,
        share,
        shapes: delivery.shapes.map((s) => ({ ...s, always: s.key === MAIN_SHAPE || share.shapes.includes(s.key) })),
      })
      adoptShare(share)
      adoptPost(await api.post(project.id))
      return share
    } catch (e) {
      fail(e)
      // Back to what was saved: a tick or a field that did not stick should not look as if it did.
      setDelivery(delivery)
      adoptShare(delivery.share)
    }
  }

  const always = (key: ShapeKey, on: boolean) => {
    if (!delivery) return
    const shapes = on ? [...delivery.share.shapes, key] : delivery.share.shapes.filter((k) => k !== key)
    // The tick stays where it was put while the brand is saved, instead of jumping back.
    setDelivery({ ...delivery, shapes: delivery.shapes.map((s) => (s.key === key ? { ...s, always: on } : s)) })
    void saveShare({ shapes })
  }

  const rewrite = async () => {
    if (post?.post?.own.length && !window.confirm('Wat je zelf in de teksten veranderd hebt, gaat dan verloren. Doorgaan?')) return
    setError(null)
    typed.current = {}
    setTexts(null)
    try {
      adoptPost(await api.rewritePost(project.id))
    } catch (e) {
      fail(e)
    }
  }

  const address = async (to: 'je' | 'u') => {
    if (!delivery || delivery.share.address === to) return
    if (post?.post?.own.length && !window.confirm('De teksten worden opnieuw geschreven; wat je zelf veranderd hebt, gaat dan verloren. Doorgaan?')) return
    const saved = await saveShare({ address: to })
    if (!saved) return
    typed.current = {}
    setTexts(null)
    try {
      adoptPost(await api.rewritePost(project.id))
    } catch (e) {
      fail(e)
    }
  }

  const copy = async () => {
    if (!texts) return
    if (await copyText(texts[platform], area.current)) {
      setCopied(platform)
      setTimeout(() => setCopied((c) => (c === platform ? null : c)), 2000)
    }
  }

  const pickPlatform = (next: Platform) => {
    setPlatform(next)
    remember(PLATFORM_KEY, next)
  }

  const shown = delivery?.shapes.find((s) => s.key === chosen) ?? null
  const view = post?.post ?? null
  const stuck = post?.job.status === 'error' && !view
  const url = (key: ShapeKey) => `${api.outputUrl(project.id, key)}${key === MAIN_SHAPE ? '?' : '&'}v=${version}`

  const linkSays = !view ? '' : link.trim()
    ? 'Deze link komt onder elke post op Facebook en WhatsApp.'
    : view.linkFrom === 'dienst'
      ? 'Leeg gelaten: de pagina waar deze dienst vandaan kwam wordt gebruikt.'
      : view.linkFrom === 'station'
        ? 'Leeg gelaten: de pagina van de kerk op Kerkdienstgemist wordt gebruikt.'
        : 'Zonder link komt er geen verwijzing naar de hele dienst onder de post.'

  return (
    <div className="sheet" role="dialog" aria-label="Klaar om te delen"
         onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sheet-box wide deliver-box">
        <header>
          <div className="sheet-title">
            <div>
              <h2>Klaar om te delen</h2>
              <p className="intro">
                {project.title ? <strong>{project.title}</strong> : 'Je clip'} staat klaar. Kies het formaat
                voor de plek waar hij komt, en neem de tekst mee.
              </p>
            </div>
            <button className="bare" onClick={onClose} aria-label="Sluiten">✕</button>
          </div>
        </header>

        <div className="sheet-body">
          {error && <div className="error">{error}</div>}
          {!delivery ? (
            <p className="empty">Bezig met laden…</p>
          ) : (
            <div className="deliver">
              <div className="deliver-stage">
                {shown && (
                  <div className="deliver-fit" style={{ width: `min(100%, ${(60 * shown.width) / shown.height}vh)` }}>
                    <div className="deliver-frame" style={{ aspectRatio: `${shown.width} / ${shown.height}` }}>
                      {shown.ready ? (
                        <video key={`${shown.key}-${version}`} className="made" src={url(shown.key)}
                               controls playsInline autoPlay muted />
                      ) : (
                        <>
                          {project.sourceInfo && project.hasFootage && <ShapeFrame project={project} shape={shown} />}
                          <div className="deliver-note">
                            {making === shown.key ? (
                              <span>Wordt gemaakt · {Math.round(renderStatus.progress * 100)}%</span>
                            ) : queue.includes(shown.key) ? (
                              <span>Staat in de wachtrij</span>
                            ) : !delivery.canMake ? (
                              <span>Deze vorm kan niet meer gemaakt worden: de opname is opgeruimd</span>
                            ) : (
                              <>
                                <span>Zo ziet het beeld eruit in {shown.ratio}</span>
                                <button className="primary" disabled={!delivery.canMake} onClick={() => make(shown.key)}>
                                  {shown.name} {shown.ratio} maken
                                </button>
                              </>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}
                {shown && (
                  <p className="stage-meta">
                    {shown.name} {shown.ratio} · {shown.width}×{shown.height}
                    {shown.ready && shown.mb !== null ? ` · ${dutchMb(shown.mb)}` : ''}
                  </p>
                )}
              </div>

              <div className="deliver-side">
                <section>
                  <h3>Video</h3>
                  <ul className="formats">
                    {delivery.shapes.map((s) => {
                      const busy = making === s.key && rendering
                      return (
                        <li key={s.key} className={`format${chosen === s.key ? ' on' : ''}`}>
                          <button className="format-pick" aria-pressed={chosen === s.key} onClick={() => setChosen(s.key)}>
                            <ShapeIcon width={s.width} height={s.height} />
                            <span className="what">
                              <strong>{s.name}<span className="ratio">{s.ratio}</span></strong>
                              <span className="use">{s.use}</span>
                            </span>
                          </button>
                          <div className="do">
                            {busy ? (
                              <span className="meta">{Math.round(renderStatus.progress * 100)}%</span>
                            ) : queue.includes(s.key) ? (
                              <span className="meta">In de wachtrij</span>
                            ) : s.ready ? (
                              <>
                                {s.stale && (
                                  <button className="small" disabled={!delivery.canMake} onClick={() => make(s.key)}
                                          title="Gemaakt vóór je laatste wijziging aan de clip">
                                    Opnieuw maken
                                  </button>
                                )}
                                <a className="button small" href={url(s.key)} download>Download</a>
                              </>
                            ) : (
                              <button className="small" disabled={!delivery.canMake} onClick={() => make(s.key)}>
                                Maken
                              </button>
                            )}
                          </div>
                          {busy && (
                            <div className="progress busy">
                              <div className="bar"><div style={{ width: `${Math.round(renderStatus.progress * 100)}%` }} /></div>
                            </div>
                          )}
                          {s.ready && s.stale && !busy && (
                            <p className="stale">Gemaakt vóór je laatste wijziging aan de clip.</p>
                          )}
                          {s.key === MAIN_SHAPE ? (
                            <p className="always-note">Wordt altijd gemaakt.</p>
                          ) : (
                            <label className="always">
                              <input type="checkbox" checked={s.always} onChange={(e) => always(s.key, e.target.checked)} />
                              Voortaan altijd meemaken bij Video maken
                            </label>
                          )}
                        </li>
                      )
                    })}
                  </ul>
                  {!delivery.canMake && (
                    <p className="hint">
                      De opname van deze clip is opgeruimd, dus er kunnen geen andere formaten meer van gemaakt worden.
                    </p>
                  )}
                </section>

                <section>
                  <h3>Tekst bij de post</h3>
                  <div className="platforms" role="tablist" aria-label="Waar je hem plaatst">
                    {PLATFORMS.map((p) => (
                      <button key={p.id} role="tab" aria-selected={platform === p.id}
                              className={platform === p.id ? 'on' : ''} onClick={() => pickPlatform(p.id)}>
                        {p.label}
                        {view?.own.includes(p.id) && <span className="own" title="Zelf aangepast"> ·</span>}
                      </button>
                    ))}
                  </div>
                  {stuck ? (
                    <div className="post-writing">
                      <p className="meta">{post?.job.error ?? 'Het schrijven van de tekst is mislukt.'}</p>
                    </div>
                  ) : writing || !texts ? (
                    <div className="post-writing">
                      <div className="progress waiting"><div className="bar"><div /></div></div>
                      <p className="meta">De tekst wordt geschreven. Dat duurt een paar tellen.</p>
                    </div>
                  ) : (
                    <textarea
                      ref={area}
                      className="post-text"
                      aria-label={`Tekst voor ${platform}`}
                      value={texts[platform]}
                      rows={11}
                      onChange={(e) => {
                        typed.current[platform] = true
                        setTexts({ ...texts, [platform]: e.target.value })
                      }}
                    />
                  )}
                  <div className="post-actions">
                    <button className="primary" onClick={copy} disabled={!texts || writing}>
                      {copied === platform ? 'Gekopieerd' : 'Kopieer tekst'}
                    </button>
                    <button onClick={rewrite} disabled={writing}>Opnieuw schrijven</button>
                  </div>
                  {view && !writing && (
                    <p className="hint">
                      {view.by === 'model'
                        ? 'Geschreven door Claude, uit wat er in de clip gezegd wordt. Lees hem na voordat je hem plaatst.'
                        : view.note || 'Een eenvoudige tekst, uit de titel van de clip.'}
                      {view.bible && <> Genoemd in de clip: <strong>{view.bible}</strong>.</>}
                    </p>
                  )}

                  <details className="post-lines">
                    <summary>Vaste regels onder elke post</summary>
                    <div className="fields wide-labels">
                      <span className="label">Aanspreekvorm</span>
                      <div className="seg address" role="group" aria-label="Aanspreekvorm">
                        {(['je', 'u'] as const).map((form) => (
                          <button key={form} className={delivery.share.address === form ? 'on' : ''}
                                  aria-pressed={delivery.share.address === form} disabled={writing}
                                  onClick={() => address(form)}>
                            {form}
                          </button>
                        ))}
                      </div>
                      <label htmlFor="post-tags">Vaste hashtags</label>
                      <input id="post-tags" value={hashtags} placeholder="#kerkdienst #utrecht"
                             onChange={(e) => setHashtags(e.target.value)}
                             onBlur={() => {
                               const typedTags = hashtags.split(/[\s,]+/).filter(Boolean)
                               if (typedTags.join(' ') !== delivery.share.hashtags.join(' ')) void saveShare({ hashtags: typedTags })
                             }} />
                      <label htmlFor="post-link">Link naar de hele dienst</label>
                      <input id="post-link" value={link} placeholder={view?.link || 'https://'}
                             onChange={(e) => setLink(e.target.value)}
                             onBlur={() => link.trim() !== delivery.share.link && saveShare({ link })} />
                      <p className="hint span">{linkSays}</p>
                    </div>
                  </details>
                </section>
              </div>
            </div>
          )}
        </div>

        <footer className="sheet-foot">
          <button className="primary" onClick={onClose}>Klaar</button>
          <span className="meta">Dit venster komt terug onder Delen en downloaden, naast Video maken.</span>
        </footer>
      </div>
    </div>
  )
}
