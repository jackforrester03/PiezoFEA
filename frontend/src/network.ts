// Complex N-port network helpers (Y/Z matrices from the backend's Y(f)).

export interface C {
  re: number
  im: number
}

export const c = (re: number, im = 0): C => ({ re, im })
export const add = (a: C, b: C): C => c(a.re + b.re, a.im + b.im)
export const sub = (a: C, b: C): C => c(a.re - b.re, a.im - b.im)
export const mul = (a: C, b: C): C => c(a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re)
export const div = (a: C, b: C): C => {
  const d = b.re * b.re + b.im * b.im
  return c((a.re * b.re + a.im * b.im) / d, (a.im * b.re - a.re * b.im) / d)
}
export const neg = (a: C): C => c(-a.re, -a.im)
export const abs = (a: C): number => Math.hypot(a.re, a.im)
export const argDeg = (a: C): number => (Math.atan2(a.im, a.re) * 180) / Math.PI

export type Matrix = C[][]

/** Inverse of a small complex matrix (Gauss-Jordan with partial pivoting). */
export function invert(m: Matrix): Matrix {
  const n = m.length
  const a = m.map((row, i) => [...row, ...Array.from({ length: n }, (_, j) => c(i === j ? 1 : 0))])
  for (let col = 0; col < n; col++) {
    let p = col
    for (let r = col + 1; r < n; r++) if (abs(a[r][col]) > abs(a[p][col])) p = r
    ;[a[col], a[p]] = [a[p], a[col]]
    const pivot = a[col][col]
    for (let k = 0; k < 2 * n; k++) a[col][k] = div(a[col][k], pivot)
    for (let r = 0; r < n; r++) {
      if (r === col) continue
      const factor = a[r][col]
      for (let k = 0; k < 2 * n; k++) a[r][k] = sub(a[r][k], mul(factor, a[col][k]))
    }
  }
  return a.map((row) => row.slice(n))
}

/** Y matrices per frequency from the backend arrays [n_f][N][N]. */
export function yMatrices(re: number[][][], im: number[][][]): Matrix[] {
  return re.map((m, i) => m.map((row, j) => row.map((v, k) => c(v, im[i][j][k]))))
}
