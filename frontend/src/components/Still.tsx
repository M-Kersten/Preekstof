import { useEffect, useState } from 'react'

interface Props {
  /** Where the picture is, or null when this service has none. */
  src: string | null
  /** Seconds of recording, to write the length over the corner. Left off when unknown. */
  length?: string
}

/**
 * The frame the platform keeps of a service, in a 16:9 box.
 *
 * Two ways to end up with nothing: a service that never had a still, and a link that no
 * longer works. The signed links Kerkdienstgemist hands out expire, and a church that is
 * offline gets no picture at all. Both land on the same quiet placeholder rather than the
 * browser's broken-image icon, because a list of Sundays with a torn-paper glyph next to
 * every row looks like the app is broken when it is the link that is stale.
 */
export default function Still({ src, length }: Props) {
  const [failed, setFailed] = useState(false)

  // A new address deserves a new attempt; without this, one stale link poisons the slot
  // for whatever service is shown there next.
  useEffect(() => setFailed(false), [src])

  return (
    <div className={`still${src && !failed ? '' : ' blank'}`}>
      {src && !failed && <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} />}
      {length && <span className="len">{length}</span>}
    </div>
  )
}
