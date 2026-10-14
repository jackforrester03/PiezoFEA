// Resonance / antiresonance pairs from a sampled |Y(f)|, for display only.

export interface Resonance {
  fr: number // Hz, |Y| local maximum (series resonance)
  fa: number // Hz, following |Y| local minimum (parallel resonance)
  keff: number // sqrt(1 - (fr/fa)^2)
  yMax: number
  yMin: number
}

/** Vertex of the parabola through three points (x, log y), for sub-step peak location. */
function refine(f: number[], m: number[], i: number): number {
  if (i <= 0 || i >= f.length - 1) return f[i]
  const [y0, y1, y2] = [Math.log(m[i - 1]), Math.log(m[i]), Math.log(m[i + 1])]
  const denom = y0 - 2 * y1 + y2
  if (denom === 0) return f[i]
  const delta = (0.5 * (y0 - y2)) / denom // in steps, assumes locally uniform spacing
  if (Math.abs(delta) > 1) return f[i]
  const h = delta > 0 ? f[i + 1] - f[i] : f[i] - f[i - 1]
  return f[i] + delta * h
}

/**
 * Each local max of |Y| paired with the lowest |Y| before the next max. Pairs whose
 * max/min ratio is below `minRatio`, or whose minimum is the last sample, are dropped.
 */
export function findResonances(f: number[], mag: number[], minRatio = 2): Resonance[] {
  const maxima: number[] = []
  for (let i = 1; i < mag.length - 1; i++) {
    if (mag[i] > mag[i - 1] && mag[i] >= mag[i + 1]) maxima.push(i)
  }
  const out: Resonance[] = []
  maxima.forEach((i, n) => {
    const end = n + 1 < maxima.length ? maxima[n + 1] : mag.length
    let j = i
    for (let q = i + 1; q < end; q++) if (mag[q] < mag[j]) j = q
    if (j === i || j >= mag.length - 1 || mag[i] / mag[j] < minRatio) return
    const fr = refine(f, mag, i)
    const fa = refine(f, mag.map((v) => 1 / v), j)
    out.push({ fr, fa, keff: fa > fr ? Math.sqrt(1 - (fr / fa) ** 2) : NaN, yMax: mag[i], yMin: mag[j] })
  })
  return out
}
