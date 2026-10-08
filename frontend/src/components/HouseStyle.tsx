interface Props {
  own: boolean
  what: string
  onOwn: (own: boolean) => void
}

/**
 * Says where a change goes. Subtitles and logo are set once for every clip (backend/house.py);
 * a clip that should look different keeps its own with the box.
 */
export default function HouseStyle({ own, what, onOwn }: Props) {
  return (
    <div className="house-style">
      <p className="hint">
        {own
          ? `Deze clip houdt ${what} voor zichzelf. Je andere clips merken niets van wat je hier verandert.`
          : `Geldt voor al je clips die nog niet gemaakt zijn, en voor elke nieuwe clip.`}
      </p>
      <label className="check">
        <input type="checkbox" checked={own} onChange={(e) => onOwn(e.target.checked)} />
        <span>Alleen voor deze clip</span>
      </label>
    </div>
  )
}
