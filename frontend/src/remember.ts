/**
 * The few things the app puts down and picks back up.
 *
 * Two kinds. A choice you made (which platform you post to) is kept for good, in
 * localStorage. Where you were (which service, which clip, which workspace) is kept only
 * while the app is open, in sessionStorage: a reload brings you back to it, and starting
 * the app fresh begins on the start screen. The desktop app keeps its storage between
 * starts (desktop/app.py), so with localStorage every new start opened the last service.
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

/** Where you are: kept while the app is open, gone when it starts fresh. */
export function heldForNow(key: string): string | null {
  try {
    // Written for good by versions before this one. Left there, it would keep opening
    // the last service on every start.
    localStorage.removeItem(PREFIX + key)
    localStorage.removeItem(BEFORE + key)
  } catch {
    /* as above */
  }
  try {
    return sessionStorage.getItem(PREFIX + key)
  } catch {
    return null
  }
}

export function holdForNow(key: string, value: string): void {
  try {
    sessionStorage.setItem(PREFIX + key, value)
  } catch {
    /* as above */
  }
}

export function letGo(key: string): void {
  try {
    sessionStorage.removeItem(PREFIX + key)
  } catch {
    /* as above */
  }
}
