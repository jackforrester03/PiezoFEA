import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'
import { useMemo, useState } from 'react'
import { abs, add, argDeg, c, div, mul, neg, sub, type Matrix } from '../network'
import { KHZ } from '../units'
import { NumberField } from './fields'

const Plot = createPlotlyComponent(Plotly)
const NF = 1e-9

interface Props {
  f: number[]
  ys: Matrix[]
  ports: string[]
  portName: (id: string) => string
}

/**
 * Two-port load analysis from Y(f): drive `inp` with V_in, load `out` with Y_L = 1/R + jwC_L,
 * all other ports shorted. Computed analytically, so changing the load needs no re-solve.
 */
export function LoadAnalysis({ f, ys, ports, portName }: Props) {
  const [inp, setInp] = useState(0)
  const [out, setOut] = useState(1)
  const [rLoad, setRLoad] = useState(1000)
  const [open, setOpen] = useState(false)
  const [cLoad, setCLoad] = useState(0)

  // Output capacitance (input shorted) at the lowest frequency, and the strongest Y_in,out resonance.
  const { cOut, fRes } = useMemo(() => {
    const y22 = ys[0][out][out]
    const cOut = y22.im / (2 * Math.PI * f[0])
    let best = 0
    ys.forEach((m, i) => {
      if (abs(m[out][inp]) > abs(ys[best][out][inp])) best = i
    })
    return { cOut, fRes: f[best] }
  }, [f, ys, inp, out])

  const curves = useMemo(() => {
    const gain: number[] = []
    const gainPh: number[] = []
    const zin: number[] = []
    const eff: number[] = []
    const pout: number[] = []
    f.forEach((fi, i) => {
      const m = ys[i]
      const w = 2 * Math.PI * fi
      const yl = c(open ? 0 : 1 / rLoad, w * cLoad)
      const denom = add(m[out][out], yl)
      const g = div(neg(m[out][inp]), denom) // V_out / V_in
      const yin = sub(m[inp][inp], div(mul(m[inp][out], m[out][inp]), denom))
      const gMag = abs(g)
      gain.push(gMag)
      gainPh.push(argDeg(g))
      zin.push(1 / abs(yin))
      const pIn = yin.re // W per V_rms^2 at the input
      const pOut = yl.re * gMag * gMag
      pout.push(pOut)
      eff.push(pIn > 0 ? (100 * pOut) / pIn : 0)
    })
    return { gain, gainPh, zin, eff, pout }
  }, [f, ys, inp, out, rLoad, open, cLoad])

  const iBest = curves.eff.reduce((b, v, i, a) => (v > a[b] ? i : b), 0)
  const iGain = curves.gain.reduce((b, v, i, a) => (v > a[b] ? i : b), 0)
  const rOpt = 1 / (2 * Math.PI * fRes * cOut)
  const x = f.map((v) => v / KHZ)
  const options = ports.map((p, i) => (
    <option key={p} value={i}>
      {portName(p)}
    </option>
  ))

  return (
    <div className="load-analysis">
      <h3>Load analysis</h3>
      <div className="load-controls">
        <label className="field">
          <span className="field-label">Drive</span>
          <select value={inp} onChange={(ev) => setInp(Number(ev.target.value))}>
            {options}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Load on</span>
          <select value={out} onChange={(ev) => setOut(Number(ev.target.value))}>
            {options}
          </select>
        </label>
        <NumberField label="R_L" unit="Ω" min={1e-6} value={rLoad} onChange={setRLoad} />
        <NumberField label="C_L (parallel)" unit="nF" scale={NF} min={0} value={cLoad} onChange={setCLoad} />
        <label className="check inline">
          <input type="checkbox" checked={open} onChange={(ev) => setOpen(ev.target.checked)} /> R_L open
        </label>
      </div>
      {inp === out ? (
        <p className="error">Choose different drive and load ports.</p>
      ) : (
        <>
          <p className="hint">
            C_out ({portName(ports[out])}, input shorted) = {(cOut / NF).toPrecision(4)} nF · strongest transfer
            resonance {(fRes / KHZ).toFixed(2)} kHz · R_opt ≈ 1/(ωC_out) = {rOpt.toPrecision(4)} Ω{' '}
            <button
              className="link"
              onClick={() => {
                setOpen(false)
                setCLoad(0)
                setRLoad(Number(rOpt.toPrecision(4)))
              }}
            >
              use
            </button>
            {ports.length > 2 && ' · other ports shorted'}
          </p>
          <table>
            <tbody>
              <tr>
                <th>Max efficiency</th>
                <td>{curves.eff[iBest].toFixed(1)} %</td>
                <td>at {x[iBest].toFixed(2)} kHz</td>
                <td>gain {curves.gain[iBest].toPrecision(4)}</td>
                <td>P_out {curves.pout[iBest].toPrecision(3)} W per V_rms²</td>
              </tr>
              <tr>
                <th>Max gain</th>
                <td>{curves.gain[iGain].toPrecision(4)}</td>
                <td>at {x[iGain].toFixed(2)} kHz</td>
                <td>η {curves.eff[iGain].toFixed(1)} %</td>
                <td>|Z_in| {curves.zin[iGain].toPrecision(4)} Ω</td>
              </tr>
            </tbody>
          </table>
          <Plot
            className="plot"
            useResizeHandler
            style={{ width: '100%', height: '520px' }}
            data={[
              { x, y: curves.gain, type: 'scatter', mode: 'lines', name: '|V_out/V_in|', line: { color: '#2e86de', width: 1.6 } },
              { x, y: curves.gainPh, type: 'scatter', mode: 'lines', name: '∠ gain (°)', yaxis: 'y2', line: { color: '#d1495b', width: 1.2 } },
              { x, y: curves.zin, type: 'scatter', mode: 'lines', name: '|Z_in| (Ω)', yaxis: 'y3', line: { color: '#e69f00', width: 1.6 } },
              { x, y: curves.eff, type: 'scatter', mode: 'lines', name: 'η (%)', yaxis: 'y4', line: { color: '#009e73', width: 1.6 } },
            ]}
            layout={{
              autosize: true,
              margin: { l: 70, r: 20, t: 10, b: 45 },
              hovermode: 'x unified',
              legend: { orientation: 'h', y: 1.06 },
              xaxis: { title: { text: 'Frequency (kHz)' }, anchor: 'y4' },
              yaxis: { title: { text: '|gain|' }, type: 'log', domain: [0.72, 1] },
              yaxis2: { title: { text: '∠ (°)' }, domain: [0.52, 0.68], range: [-185, 185], dtick: 90 },
              yaxis3: { title: { text: '|Z_in| (Ω)' }, type: 'log', domain: [0.26, 0.48] },
              yaxis4: { title: { text: 'η (%)' }, domain: [0, 0.22], range: [0, 100] },
            }}
            config={{ displaylogo: false, responsive: true }}
          />
        </>
      )}
    </div>
  )
}
