// The colour correction of backend/look.py, imitated in the browser for the preview.
//
// The render stretches the brightness only: y -> (y - low) * gain + 16, and multiplies the
// colour by `colour`. A browser shows video range 16..235 as 0..1, so on screen that is
// v -> gain * v + gain * (16 - low) / 219. CSS brightness(b) followed by contrast(c) gives
// v -> b * c * v + (1 - c) / 2, which is the same line for c = 1 - 2d and b = gain / c. CSS
// does this to red, green and blue each, which stretches the colour by `gain` as well, so
// saturate() takes that back out again. Close, not pixel for pixel.

export interface Look {
  low: number
  gain: number
  colour: number
}

export function cssFilter(look: Look | null): string | undefined {
  if (!look) return undefined
  const offset = (look.gain * (16 - look.low)) / 219
  const contrast = 1 - 2 * offset
  const brightness = look.gain / contrast
  const saturate = look.colour / look.gain
  const r = (n: number) => Math.round(n * 1000) / 1000
  return `brightness(${r(brightness)}) contrast(${r(contrast)}) saturate(${r(saturate)})`
}
