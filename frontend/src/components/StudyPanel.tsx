import type { EigenSettings, HarmonicSettings, Study } from '../api/types'
import { useStore } from '../store'
import { KHZ, MM } from '../units'
import { NumberField, Section, SelectField } from './fields'

const DEFAULT_EIGEN: EigenSettings = { num_modes: 20, freq_shift: 1000, port_condition: 'short' }
const DEFAULT_HARMONIC: HarmonicSettings = { f_start: 20e3, f_stop: 200e3, n_points: 181, spacing: 'lin' }

export function StudyPanel() {
  const study = useStore((s) => s.project.study)
  const terminals = useStore((s) => s.project.terminals)
  const setStudy = useStore((s) => s.setStudy)
  const set = (patch: Partial<Study>) => setStudy({ ...study, ...patch })
  const eig = study.eigen
  const harm = study.harmonic
  const mesh = study.mesh ?? { max_element_size: 0.5e-3, elements_per_wavelength_at_f_max: 10, order: 2 }
  const portTerminals = terminals.filter((t) => t.role === 'port')
  const ports = (study.ports ?? []).filter((p) => portTerminals.some((t) => t.id === p))

  return (
    <Section title="Study">
      <label className="check">
        <input type="checkbox" checked={!!eig} onChange={(ev) => set({ eigen: ev.target.checked ? DEFAULT_EIGEN : null })} />
        Eigenfrequencies
      </label>
      {eig && (
        <div className="grid2 indent">
          <NumberField label="Modes" integer min={1} value={eig.num_modes ?? 20} onChange={(num_modes) => set({ eigen: { ...eig, num_modes } })} />
          <NumberField
            label="Search from"
            unit="kHz"
            scale={KHZ}
            min={0}
            value={eig.freq_shift ?? 1000}
            onChange={(freq_shift) => set({ eigen: { ...eig, freq_shift } })}
            title="Shift: modes nearest this frequency are found first"
          />
          <SelectField
            label="Ports"
            value={eig.port_condition ?? 'short'}
            options={[
              { value: 'short', label: 'shorted (f_r)' },
              { value: 'open', label: 'open (f_a)' },
            ]}
            onChange={(port_condition) => set({ eigen: { ...eig, port_condition } })}
          />
        </div>
      )}

      <label className="check">
        <input
          type="checkbox"
          checked={!!harm}
          onChange={(ev) => set({ harmonic: ev.target.checked ? DEFAULT_HARMONIC : null })}
        />
        Admittance sweep (harmonic)
      </label>
      {harm && (
        <div className="grid2 indent">
          <NumberField label="Start" unit="kHz" scale={KHZ} min={0} value={harm.f_start} onChange={(f_start) => set({ harmonic: { ...harm, f_start } })} />
          <NumberField label="Stop" unit="kHz" scale={KHZ} min={0} value={harm.f_stop} onChange={(f_stop) => set({ harmonic: { ...harm, f_stop } })} />
          <NumberField label="Points" integer min={1} value={harm.n_points} onChange={(n_points) => set({ harmonic: { ...harm, n_points } })} />
          <SelectField
            label="Spacing"
            value={harm.spacing ?? 'lin'}
            options={['lin', 'log'] as const}
            onChange={(spacing) => set({ harmonic: { ...harm, spacing } })}
          />
          {harm.n_points > 1 && (
            <p className="hint span2">
              Step {((harm.f_stop - harm.f_start) / (harm.n_points - 1) / KHZ).toPrecision(3)} kHz
              {harm.spacing === 'log' ? ' (average; log spacing)' : ''}
            </p>
          )}
          {portTerminals.length > 1 && (
            <div className="span2">
              <span className="field-label">Ports to drive (none ticked = all)</span>
              {portTerminals.map((t) => (
                <label key={t.id} className="check inline">
                  <input
                    type="checkbox"
                    checked={ports.includes(t.id)}
                    onChange={(ev) =>
                      set({ ports: ev.target.checked ? [...ports, t.id] : ports.filter((p) => p !== t.id) })
                    }
                  />
                  {t.name || t.id}
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      <h3>Mesh</h3>
      <div className="grid2">
        <NumberField
          label="Max element size"
          unit="mm"
          scale={MM}
          min={0}
          value={mesh.max_element_size ?? 0.5e-3}
          onChange={(max_element_size) => set({ mesh: { ...mesh, max_element_size } })}
        />
        <NumberField
          label="Elements / shear λ"
          min={1}
          value={mesh.elements_per_wavelength_at_f_max ?? 10}
          onChange={(v) => set({ mesh: { ...mesh, elements_per_wavelength_at_f_max: v } })}
          title="At the sweep's stop frequency (or f_max)"
        />
        <SelectField
          label="Order"
          value={String(mesh.order ?? 2) as '1' | '2'}
          options={[
            { value: '2', label: 'quadratic' },
            { value: '1', label: 'linear' },
          ]}
          onChange={(o) => set({ mesh: { ...mesh, order: Number(o) as 1 | 2 } })}
        />
      </div>
    </Section>
  )
}
