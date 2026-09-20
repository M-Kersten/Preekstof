/**
 * The few things the app puts down and picks back up: which clip you had open, which
 * service, which of the two workspaces you were in.
 *
 * All of it is kept under one prefix. The app was called something else before, so a key
 * written under the old name is moved across the first time it is asked for: reopening the
 * app after an update should land you where you left off, not on an empty page.
 *
 * Every call is wrapped, because localStorage throws rather than returns null in a private
 * window and in a browser with site data blocked. Forgetting where you were is a small
 * disappointment; a white screen is not.
 */
const PREFIX = 'preekstof.'
const BEFORE = 'church-reel-maker.'

export function remembered(key: string): string | null {
  try {
    const now = localStorage.getItem(PREFIX + key)
    if (now !== null) return now
    const older = localStorage.getItem(BEFORE + key)
    if (older === null) return null
    localStorage.setItem(PREFIX + key, older)
    localStorage.removeItem(BEFORE + key)
    return older
  } catch {
    return null
  }
}

export function remember(key: string, value: string): void {
  try {
    localStorage.setItem(PREFIX + key, value)
  } catch {
    /* nothing to be done about it, and nothing worth stopping for */
  }
}

export function forget(key: string): void {
  try {
    localStorage.removeItem(PREFIX + key)
    localStorage.removeItem(BEFORE + key)
  } catch {
    /* as above */
  }
}
