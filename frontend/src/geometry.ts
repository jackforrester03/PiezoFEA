// r-z cross-section helpers for the preview. The backend interpreter (geometry/axisym.py)
// remains the authority; this only draws what the user has entered.
import type { Body, Electrode } from './api/types'

export interface Rect {
  r0: number
  r1: number
  z0: number
  z1: number
}

export function bodyRect(b: Body): Rect {
  const z0 = b.params.z_offset ?? 0
  if (b.shape === 'disc') return { r0: 0, r1: b.params.radius, z0, z1: z0 + b.params.thickness }
  return { r0: b.params.inner_radius, r1: b.params.outer_radius, z0, z1: z0 + b.params.thickness }
}

/** Electrode as a segment [(r, z), (r, z)] on its body's boundary. */
export function electrodeSegment(e: Electrode, b: Body): [[number, number], [number, number]] {
  const r = bodyRect(b)
  const x = e.extent
  if (x.kind === 'annulus') {
    const z = e.surface === 'top' ? r.z1 : r.z0
    return [
      [x.r_min, z],
      [x.r_max, z],
    ]
  }
  const rr = e.surface === 'outer' ? r.r1 : r.r0
  return [
    [rr, r.z0 + x.z_min],
    [rr, r.z0 + x.z_max],
  ]
}

/** Extent covering the whole of a face. */
export function fullFaceExtent(surface: Electrode['surface'], b: Body): Electrode['extent'] {
  const r = bodyRect(b)
  if (surface === 'top' || surface === 'bottom') {
    return { kind: 'annulus', r_min: r.r0, r_max: r.r1, theta_min: 0, theta_max: 360 }
  }
  return { kind: 'band', z_min: 0, z_max: r.z1 - r.z0, theta_min: 0, theta_max: 360 }
}

export function uniqueId(prefix: string, taken: string[]): string {
  let i = 1
  while (taken.includes(`${prefix}${i}`)) i++
  return `${prefix}${i}`
}
