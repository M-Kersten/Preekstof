import { useEffect, useState } from 'react'
import { api } from '../api'

/**
 * Says so when the interface and the server behind it come from different code.
 *
 * The interface is read from disk on every page load; the server keeps running the code it
 * started with. Update the files while the black window is open and the page shows buttons
 * the server has never heard of: a tab that goes white, a window that says "Not Found".
 * Nothing in either of those tells a volunteer that closing one window is the whole fix.
 *
 * Between two releases the version number stays the same, so the fingerprint of the server
 * code is compared as well (backend/version.py).
 */
export default function Outdated() {
  const [running, setRunning] = useState<{ version: string; build?: string } | null>(null)
  useEffect(() => {
    api.health().then((h) => setRunning({ version: h.version, build: h.build })).catch(() => setRunning(null))
  }, [])
  if (!running) return null
  const otherVersion = Boolean(__BUILT_VERSION__) && !running.version.startsWith(__BUILT_VERSION__)
  // A server that sends no fingerprint at all is from before there was one: older code too.
  const otherCode = Boolean(__BUILT_FROM__) && running.build !== __BUILT_FROM__
  if (!otherVersion && !otherCode) return null
  return (
    <div className="outdated" role="alert">
      {otherVersion
        ? `De app is bijgewerkt naar ${__BUILT_VERSION__}, maar het zwarte venster draait nog ${running.version}.`
        : 'De app is bijgewerkt, maar het zwarte venster draait nog de code van daarvoor.'}{' '}
      Sluit het zwarte venster en start de app opnieuw; tot dan werkt niet alles.
    </div>
  )
}
