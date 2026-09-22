interface Props {
  /** The failure this report is about, in the app's own words. */
  trouble?: string
  /** The service it happened on, when it happened on one. */
  service?: string
  /** Quieter styling for a button that sits under an error message. */
  small?: boolean
}

/**
 * "Er ging iets mis" — one zip, saved where the browser saves things, for a volunteer to
 * attach to a mail.
 *
 * A plain link and not a fetch: the browser then handles the download itself, says where
 * it landed, and the file survives a page that reloads underneath it. Nothing is sent
 * anywhere; this is the whole of what leaves the building, and only because a person
 * clicked and then attached it.
 */
export default function Report({ trouble = '', service = '', small = false }: Props) {
  const asked = new URLSearchParams()
  if (trouble) asked.set('trouble', trouble)
  if (service) asked.set('service', service)
  const where = `/diagnose${asked.toString() ? `?${asked}` : ''}`

  return (
    <a className={`report${small ? ' small' : ''}`} href={where} download>
      Melding opslaan
    </a>
  )
}
