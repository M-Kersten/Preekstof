import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * Says so when the interface is newer than the server behind it.
 *
 * The interface is read from disk on every page load; the server keeps running the code it
 * started with. Update the files while the black window is open and the page shows buttons
 * the server has never heard of: a tab that goes white, a window that says "Not Found".
 * Nothing in either of those tells a volunteer that closing one window is the whole fix.
 */
export default function Outdated() {
  const [running, setRunning] = useState<string | null>(null)
  useEffect(() => {
    api.health().then((h) => setRunning(h.version)).catch(() => setRunning(null))
  }, [])
  if (!running || !__BUILT_VERSION__ || running.startsWith(__BUILT_VERSION__)) return null
  return (
    <div className="outdated" role="alert">
      De app is bijgewerkt naar {__BUILT_VERSION__}, maar het zwarte venster draait nog {running}. Sluit het
      zwarte venster en start de app opnieuw; tot dan werkt niet alles.
    </div>
  )
}
