// The UI shows mm and kHz; the project is stored in SI.
export const MM = 1e-3
export const KHZ = 1e3

/** Compact display of a scaled number without float noise (e.g. 10.5, not 10.500000001). */
export function fmt(value: number, digits = 6): string {
  if (!Number.isFinite(value)) return ''
  return String(Number(value.toPrecision(digits)))
}
