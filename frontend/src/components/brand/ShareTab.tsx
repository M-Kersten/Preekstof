import type { ShapeKey, ShareSettings } from '../../api'

interface Props {
  share: ShareSettings
  onChange: (patch: Partial<ShareSettings>) => void
}

const EXTRA: { key: ShapeKey; name: string; use: string }[] = [
  { key: '4x5', name: 'Tijdlijn 4:5', use: 'De tijdlijn van Facebook en Instagram' },
  { key: '1x1', name: 'Vierkant 1:1', use: 'Facebook op de computer, de website en een nieuwsbrief' },
]

/**
 * How this church puts its clips out. The same settings sit in the window that opens after
 * Video maken, where the need for them shows up; here they can be found again later.
 */
export default function ShareTab({ share, onChange }: Props) {
  const toggle = (key: ShapeKey, on: boolean) =>
    onChange({ shapes: on ? [...share.shapes, key] : share.shapes.filter((k) => k !== key) })

  return (
    <>
      <p className="tab-intro">
        Wat er gebeurt als je op Video maken drukt, en welke regels er onder elke posttekst komen.
      </p>

      <div className="group">
        <h3>Formaten</h3>
        <p className="hint">
          De staande video wordt altijd gemaakt. Elk formaat dat je hier aanzet komt er bij elke clip bij, en maakt
          het wachten op Video maken wat langer.
        </p>
        {EXTRA.map((shape) => (
          <label key={shape.key} className="check">
            <input type="checkbox" checked={share.shapes.includes(shape.key)}
                   onChange={(e) => toggle(shape.key, e.target.checked)} />
            <span><strong>{shape.name}</strong> <span className="meta">· {shape.use}</span></span>
          </label>
        ))}
      </div>

      <div className="group">
        <h3>Posttekst</h3>
        <div className="fields wide-labels">
          <span className="label">Aanspreekvorm</span>
          <div className="seg address" role="group" aria-label="Aanspreekvorm">
            {(['je', 'u'] as const).map((form) => (
              <button key={form} className={share.address === form ? 'on' : ''} aria-pressed={share.address === form}
                      onClick={() => onChange({ address: form })}>
                {form}
              </button>
            ))}
          </div>

          <label htmlFor="share-tags">Vaste hashtags</label>
          <input
            id="share-tags"
            value={share.hashtags.join(' ')}
            placeholder="#kerkdienst #utrecht"
            onChange={(e) => onChange({ hashtags: e.target.value.split(/[\s,]+/) })}
          />
          <p className="hint span">
            Komen onder elke post op Instagram, samen met een paar die bij de clip zelf horen. Op Facebook alleen deze.
          </p>

          <label htmlFor="share-link">Link naar de diensten</label>
          <input
            id="share-link"
            value={share.link}
            placeholder="https://"
            onChange={(e) => onChange({ link: e.target.value })}
          />
          <p className="hint span">
            Leeg gelaten krijgt elke clip de pagina van zijn eigen dienst, als die van Kerkdienstgemist of een andere
            site kwam. Vul je hier iets in, dan komt die link onder elke post.
          </p>
        </div>
      </div>
    </>
  )
}
