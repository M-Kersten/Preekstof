/** The preview's imitation of the colour correction: the same line through the same points. */
import { cssFilter } from '../src/look.ts'

const problems: string[] = []
let checked = 0
const near = (what: string, got: number, wanted: number) => {
  checked += 1
  if (Math.abs(got - wanted) > 0.002) problems.push(`${what}: wanted ${wanted}, got ${got}`)
}

const look = { low: 35, gain: 1.23, colour: 1.2 }
const css = cssFilter(look)!
const [b, c, s] = [...css.matchAll(/\(([\d.]+)\)/g)].map((m) => Number(m[1]))
const shown = (y: number) => (y - 16) / 219
const css_ = (v: number) => (b * v - 0.5) * c + 0.5
const render = (y: number) => shown((y - look.low) * look.gain + 16)

near('the darkest that occurs becomes black', css_(shown(35)), render(35))
near('the middle lands where the render puts it', css_(shown(120)), render(120))
near('the brightest lands where the render puts it', css_(shown(213)), render(213))
near('the colour stretch of CSS is taken back out', s * look.gain, look.colour)
checked += 1
if (cssFilter(null) !== undefined) problems.push('no correction is no filter')

if (problems.length) {
  console.error(problems.join('\n'))
  process.exit(1)
}
console.log(`look: ${checked} checks passed`)
