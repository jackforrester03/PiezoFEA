import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'
import { useMemo, useState } from 'react'
import type { JobResults } from '../api/types'
import { abs, argDeg, invert, yMatrices } from '../network'
import { findResonances } from '../resonances'
import { useStore } from '../store'
import { KHZ } from '../units'
import { LoadAnalysis } from './LoadAnalysis'

const Plot = createPlotlyComponent(Plotly)

type Quantity = 'Y' | 'Z'

interface Entry {
  j: number
  k: number
}

export function ResponsePlot() {
  const results = useStore((s) => s.results)
  const jobId = useStore((s) => s.resultsJobId)
  const terminals = useStore((s) => s.project.terminals)

  if (!results) {
    return (
      <div className="placeholder">
        Run a simulation (or load a previous run) to see the impedance spectrum and eigenfrequencies.
      </div>
    )
  }
  const name = (id: string) => terminals.find((t) => t.id === id)?.name || id
  return <ResultsView key={jobId} results={results} jobId={jobId ?? ''} portName={name} />
}

function ResultsView({
  results,
  jobId,
  portName,
}: {
  results: JobResults
  jobId: string
  portName: (id: string) => string
}) {
  const ports = results.ports
  const harm = results.harmonic
  const [entry, setEntry] = useState<Entry>({ j: 0, k: 0 })
  const [quantity, setQuantity] = useState<Quantity>('Z')
  const [logX, setLogX] = useState(false)
  const diagonal = entry.j === entry.k

  const eigenActive = useMemo(() => {
    const e = results.eigen
    if (!e) return []
    const charges = Object.values(e.port_charge)
    const q = e.frequencies.map((_, i) => Math.max(0, ...charges.map((c) => c[i])))
    const qmax = Math.max(0, ...q)
    return e.frequencies.filter((_, i) => qmax === 0 || q[i] > 1e-2 * qmax)
  }, [results.eigen])

  const ys = useMemo(() => (harm ? yMatrices(harm.Y_real, harm.Y_imag) : null), [harm])
  // Z = Y^-1: open-circuit impedance parameters (equals 1/Y for a single port).
  const zs = useMemo(() => (ys ? ys.map(invert) : null), [ys])

  const curve = useMemo(() => {
    if (!harm || !ys || !zs) return null
    const f = harm.frequencies
    const useZ = quantity === 'Z'
    const vals = (useZ ? zs : ys).map((m) => m[entry.j][entry.k])
    const mag = vals.map(abs)
    const phase = vals.map(argDeg)
    // Driving-point admittance magnitude for resonance detection (|Y| max = |Z| min).
    const yMag = useZ ? mag.map((v) => 1 / v) : mag
    // Low-frequency capacitance of the driving point: C = Im(Y) / w, with Y = 1/Z in Z mode.
    const x0 = vals[0]
    const y0im = useZ ? -x0.im / (x0.re * x0.re + x0.im * x0.im) : x0.im
    return { f, mag, phase, useZ, resonances: diagonal ? findResonances(f, yMag) : [], c0: y0im / (2 * Math.PI * f[0]) }
  }, [harm, ys, zs, entry, quantity, diagonal])

  const label = `${quantity}${entry.j + 1}${entry.k + 1}`
  const otherPorts = ports.length > 1 ? (quantity === 'Z' ? ', other ports open' : ', other ports shorted') : ''
  const fRange = harm ? [harm.frequencies[0], harm.frequencies[harm.frequencies.length - 1]] : null
  const shapes = eigenActive
    .filter((f) => !fRange || (f >= fRange[0] && f <= fRange[1]))
    .map((f) => ({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: f / KHZ,
      x1: f / KHZ,
      y0: 0,
      y1: 1,
      line: { color: 'rgba(120,120,120,0.45)', width: 1, dash: 'dot' },
    }))

  return (
    <div className="results">
      <div className="results-toolbar">
        <span className="hint">
          job <code>{jobId}</code>
        </span>
        {harm && ports.length > 1 && (
          <select
            value={`${entry.j},${entry.k}`}
            onChange={(ev) => {
              const [j, k] = ev.target.value.split(',').map(Number)
              setEntry({ j, k })
            }}
          >
            {ports.flatMap((pj, j) =>
              ports.map((pk, k) => (
                <option key={`${j},${k}`} value={`${j},${k}`}>
                  {quantity}
                  {j + 1}
                  {k + 1}: {quantity === 'Z' ? 'V' : 'I'} at {portName(pj)} / {quantity === 'Z' ? 'I' : 'V'} at{' '}
                  {portName(pk)}
                </option>
              )),
            )}
          </select>
        )}
        {harm && (
          <>
            <div className="toggle">
              {(['Z', 'Y'] as const).map((q) => (
                <button
                  key={q}
                  className={quantity === q ? 'active' : ''}
                  onClick={() => setQuantity(q)}
                  title={q === 'Z' ? 'Z = Y⁻¹ (open-circuit parameters)' : 'Y (short-circuit parameters)'}
                >
                  {q === 'Z' ? 'Impedance' : 'Admittance'}
                </button>
              ))}
            </div>
            <label className="check inline">
              <input type="checkbox" checked={logX} onChange={(ev) => setLogX(ev.target.checked)} /> log f
            </label>
          </>
        )}
      </div>

      {curve ? (
        <Plot
          className="plot"
          useResizeHandler
          style={{ width: '100%', height: '460px' }}
          data={[
            {
              x: curve.f.map((v) => v / KHZ),
              y: curve.mag,
              type: 'scatter',
              mode: 'lines',
              name: `|${label}|`,
              line: { color: '#2e86de', width: 1.6 },
              hovertemplate: `%{x:.3f} kHz<br>|${label}| = %{y:.4~e} ${curve.useZ ? 'Ω' : 'S'}<extra></extra>`,
            },
            {
              x: curve.f.map((v) => v / KHZ),
              y: curve.phase,
              type: 'scatter',
              mode: 'lines',
              name: `∠${label}`,
              yaxis: 'y2',
              line: { color: '#d1495b', width: 1.4 },
              hovertemplate: `%{x:.3f} kHz<br>∠${label} = %{y:.1f}°<extra></extra>`,
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 70, r: 20, t: 10, b: 45 },
            showlegend: false,
            hovermode: 'x unified',
            xaxis: { title: { text: 'Frequency (kHz)' }, type: logX ? 'log' : 'linear', anchor: 'y2' },
            yaxis: {
              title: { text: `|${label}| (${curve.useZ ? 'Ω' : 'S'})` },
              type: 'log',
              domain: [0.34, 1],
              exponentformat: 'power',
            },
            yaxis2: { title: { text: 'Phase (°)' }, domain: [0, 0.26], range: [-95, 95], dtick: 45 },
            shapes,
          }}
          config={{ displaylogo: false, responsive: true }}
        />
      ) : (
        <div className="placeholder">No harmonic sweep in this run.</div>
      )}

      <div className="tables">
        {curve && diagonal && (
          <div>
            <h3>
              Resonances in sweep ({label}
              {otherPorts})
            </h3>
            <p className="hint">
              C at {(curve.f[0] / KHZ).toPrecision(4)} kHz: {(curve.c0 * 1e9).toPrecision(4)} nF · f_r at |Z| min, f_a
              at |Z| max, refined between samples
            </p>
            {curve.resonances.length ? (
              <table>
                <thead>
                  <tr>
                    <th>f_r (kHz)</th>
                    <th>f_a (kHz)</th>
                    <th>k_eff</th>
                    <th>|Z| at f_r</th>
                    <th>|Z| at f_a</th>
                  </tr>
                </thead>
                <tbody>
                  {curve.resonances.map((r) => (
                    <tr key={r.fr}>
                      <td>{(r.fr / KHZ).toFixed(2)}</td>
                      <td>{(r.fa / KHZ).toFixed(2)}</td>
                      <td>{Number.isFinite(r.keff) ? r.keff.toFixed(3) : '–'}</td>
                      <td>{fmtOhm(1 / r.yMax)}</td>
                      <td>{fmtOhm(1 / r.yMin)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="hint">No resonance/antiresonance pair inside the sweep.</p>
            )}
          </div>
        )}
        {results.eigen && (
          <div>
            <h3>Eigenfrequencies ({results.eigen.port_condition === 'open' ? 'ports open' : 'ports shorted'})</h3>
            <p className="hint">Electrically active modes only (dotted lines on the plot)</p>
            <div className="mode-list">
              {eigenActive.map((f) => (
                <span key={f}>{(f / KHZ).toFixed(2)}</span>
              ))}
            </div>
          </div>
        )}
        {harm && ports.length > 1 && (
          <p className="hint">
            Reciprocity error max|Y_jk − Y_kj|/max|Y|: {harm.reciprocity_error.toExponential(2)} · charge balance error:{' '}
            {(harm.charge_balance_error ?? 0).toExponential(1)}
          </p>
        )}
      </div>
      {harm && ys && ports.length > 1 && (
        <LoadAnalysis f={harm.frequencies} ys={ys} ports={ports} portName={portName} />
      )}
    </div>
  )
}

function fmtOhm(v: number): string {
  if (v >= 1e6) return `${(v / 1e6).toPrecision(3)} MΩ`
  if (v >= 1e3) return `${(v / 1e3).toPrecision(3)} kΩ`
  return `${v.toPrecision(3)} Ω`
}
