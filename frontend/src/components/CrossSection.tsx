import type { Body } from '../api/types'
import { bodyRect, electrodeSegment } from '../geometry'
import { useStore } from '../store'
import { terminalColor } from './colors'

const W = 640
const H = 220
const PAD = 28

/** r-z half cross-section (axis on the left), true aspect ratio, electrodes coloured by terminal. */
export function CrossSection() {
  const { bodies, electrodes, terminals } = useStore((s) => s.project)
  if (!bodies.length) return null

  const rects = bodies.map((b) => ({ b, ...bodyRect(b) }))
  const rMax = Math.max(...rects.map((r) => r.r1))
  const zMin = Math.min(...rects.map((r) => r.z0))
  const zMax = Math.max(...rects.map((r) => r.z1))
  const k = Math.min((W - 2 * PAD) / rMax, (H - 2 * PAD) / Math.max(zMax - zMin, 1e-9))
  const x = (r: number) => PAD + r * k
  const y = (z: number) => H - PAD - (z - zMin) * k
  const byId = new Map<string, Body>(bodies.map((b) => [b.id, b]))

  return (
    <figure className="cross-section">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="r-z cross-section">
        <line x1={x(0)} x2={x(0)} y1={8} y2={H - 8} className="axis-line" />
        <text x={x(0) + 4} y={14} className="label">
          axis (r = 0)
        </text>
        {rects.map(({ b, r0, r1, z0, z1 }) => (
          <g key={b.id}>
            <rect x={x(r0)} y={y(z1)} width={(r1 - r0) * k} height={(z1 - z0) * k} className="body" />
            <text x={x((r0 + r1) / 2)} y={y((z0 + z1) / 2) + 4} className="label center">
              {b.id} · {b.material_id} · {b.poling?.direction === '-z' ? '↓' : '↑'}P
            </text>
          </g>
        ))}
        {electrodes.map((e) => {
          const b = byId.get(e.body_id)
          if (!b) return null
          const [[ra, za], [rb, zb]] = electrodeSegment(e, b)
          return (
            <line
              key={e.id}
              x1={x(ra)}
              y1={y(za)}
              x2={x(rb)}
              y2={y(zb)}
              stroke={terminalColor(terminals, e.terminal_id)}
              className="electrode"
            >
              <title>
                {e.id} → {terminals.find((t) => t.id === e.terminal_id)?.name || e.terminal_id}
              </title>
            </line>
          )
        })}
        <text x={x(rMax)} y={H - 8} className="label end">
          r = {(rMax * 1e3).toPrecision(4)} mm
        </text>
      </svg>
      <figcaption>
        {terminals.map((t) => (
          <span key={t.id} className="legend-item">
            <span className="swatch" style={{ background: terminalColor(terminals, t.id) }} />
            {t.name || t.id} ({t.role})
          </span>
        ))}
      </figcaption>
    </figure>
  )
}
