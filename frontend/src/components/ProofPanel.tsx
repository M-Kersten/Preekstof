import SelfTest from './SelfTest'

/**
 * The proof, in the sheet the rest of the app uses for things you open and close again.
 *
 * It lives one click from the readiness panel, because that is where somebody already goes
 * when they are wondering whether this machine can do the work. The panel answers that with
 * a list of files that exist; this answers it by doing the work.
 */
export default function ProofPanel({ onClose }: { onClose: () => void }) {
  return (
    <div className="sheet" role="dialog" aria-label="De proef">
      <div className="sheet-box">
        <header>
          <div>
            <h2>De proef</h2>
            <p className="intro">
              Voordat je er een dienst van anderhalf uur in zet.
            </p>
          </div>
          <button className="bare" onClick={onClose} aria-label="Sluiten">✕</button>
        </header>
        <SelfTest />
      </div>
    </div>
  )
}
