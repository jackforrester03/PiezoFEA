import { useState } from 'react'
import type { Electrode, Terminal } from '../api/types'
import { fullFaceExtent } from '../geometry'
import { useStore } from '../store'
import { MM } from '../units'
import { NumberField, Section, SelectField } from './fields'
import { terminalColor } from './colors'

const SURFACES = ['top', 'bottom', 'outer', 'inner'] as const
const ROLES = ['port', 'ground', 'floating'] as const

export function ElectrodeEditor() {
  const project = useStore((s) => s.project)
  const updateElectrode = useStore((s) => s.updateElectrode)
  const addElectrode = useStore((s) => s.addElectrode)
  const removeElectrode = useStore((s) => s.removeElectrode)
  const updateTerminal = useStore((s) => s.updateTerminal)
  const addTerminal = useStore((s) => s.addTerminal)
  const removeTerminal = useStore((s) => s.removeTerminal)
  const [error, setError] = useState<string | null>(null)

  return (
    <>
      <Section
        title="Terminals"
        actions={
          <button className="small" onClick={addTerminal}>
            + Terminal
          </button>
        }
      >
        <p className="hint">Electrodes on the same terminal are tied together. Each port is driven in turn for Y(f).</p>
        {project.terminals.map((t, i) => (
          <TerminalRow
            key={t.id}
            terminal={t}
            color={terminalColor(project.terminals, t.id)}
            onChange={(nt) => updateTerminal(t.id, nt)}
            onRemove={
              project.terminals.length > 1
                ? () => setError(removeTerminal(t.id))
                : undefined
            }
            index={i}
          />
        ))}
        {error && <p className="error">{error}</p>}
      </Section>

      <Section
        title="Electrodes"
        actions={
          <button className="small" onClick={addElectrode}>
            + Electrode
          </button>
        }
      >
        {project.electrodes.map((e) => (
          <ElectrodeCard
            key={e.id}
            electrode={e}
            onChange={(ne) => updateElectrode(e.id, ne)}
            onRemove={() => removeElectrode(e.id)}
          />
        ))}
        {!project.electrodes.length && <p className="hint">No electrodes yet.</p>}
      </Section>
    </>
  )
}

function TerminalRow({
  terminal,
  color,
  onChange,
  onRemove,
}: {
  terminal: Terminal
  color: string
  onChange: (t: Terminal) => void
  onRemove?: () => void
  index: number
}) {
  return (
    <div className="row terminal-row">
      <span className="swatch" style={{ background: color }} />
      <input
        className="grow"
        value={terminal.name ?? ''}
        placeholder={terminal.id}
        onChange={(ev) => onChange({ ...terminal, name: ev.target.value })}
        aria-label="Terminal name"
      />
      <select
        value={terminal.role}
        onChange={(ev) => onChange({ ...terminal, role: ev.target.value as Terminal['role'] })}
        aria-label="Terminal role"
      >
        {ROLES.map((r) => (
          <option key={r}>{r}</option>
        ))}
      </select>
      {onRemove && (
        <button className="link danger" onClick={onRemove} title="Remove terminal">
          ✕
        </button>
      )}
    </div>
  )
}

function ElectrodeCard({
  electrode: e,
  onChange,
  onRemove,
}: {
  electrode: Electrode
  onChange: (e: Electrode) => void
  onRemove: () => void
}) {
  const bodies = useStore((s) => s.project.bodies)
  const terminals = useStore((s) => s.project.terminals)
  const body = bodies.find((b) => b.id === e.body_id) ?? bodies[0]
  const x = e.extent

  return (
    <div className="card" style={{ borderLeftColor: terminalColor(terminals, e.terminal_id) }}>
      <div className="card-title">
        <code>{e.id}</code>
        <span className="row">
          <button
            className="link"
            onClick={() => onChange({ ...e, extent: fullFaceExtent(e.surface, body) })}
            title="Cover the whole face"
          >
            full face
          </button>
          <button className="link danger" onClick={onRemove}>
            remove
          </button>
        </span>
      </div>
      <div className="grid2">
        <SelectField
          label="Body"
          value={e.body_id}
          options={bodies.map((b) => b.id)}
          onChange={(body_id) => {
            const nb = bodies.find((b) => b.id === body_id)!
            onChange({ ...e, body_id, extent: fullFaceExtent(e.surface, nb) })
          }}
        />
        <SelectField
          label="Surface"
          value={e.surface}
          options={SURFACES}
          onChange={(surface) => onChange({ ...e, surface, extent: fullFaceExtent(surface, body) })}
        />
        {x.kind === 'annulus' ? (
          <>
            <NumberField
              label="r min"
              unit="mm"
              scale={MM}
              min={0}
              value={x.r_min}
              onChange={(r_min) => onChange({ ...e, extent: { ...x, r_min } })}
            />
            <NumberField
              label="r max"
              unit="mm"
              scale={MM}
              min={0}
              value={x.r_max}
              onChange={(r_max) => onChange({ ...e, extent: { ...x, r_max } })}
            />
          </>
        ) : (
          <>
            <NumberField
              label="z min (from body bottom)"
              unit="mm"
              scale={MM}
              min={0}
              value={x.z_min}
              onChange={(z_min) => onChange({ ...e, extent: { ...x, z_min } })}
            />
            <NumberField
              label="z max"
              unit="mm"
              scale={MM}
              min={0}
              value={x.z_max}
              onChange={(z_max) => onChange({ ...e, extent: { ...x, z_max } })}
            />
          </>
        )}
      </div>
      <SelectField
        label="Terminal"
        value={e.terminal_id}
        options={terminals.map((t) => ({ value: t.id, label: `${t.name || t.id} (${t.role})` }))}
        onChange={(terminal_id) => onChange({ ...e, terminal_id })}
      />
    </div>
  )
}
