import { useState, type ReactNode } from 'react'
import { fmt } from '../units'

interface NumberFieldProps {
  label: string
  /** Value in SI units. */
  value: number
  onChange: (si: number) => void
  /** Display unit factor: shown = value / scale (e.g. 1e-3 to show metres as mm). */
  scale?: number
  unit?: string
  integer?: boolean
  min?: number
  title?: string
}

/** Numeric input that keeps the typed text while editing and commits valid numbers. */
export function NumberField({ label, value, onChange, scale = 1, unit, integer, min, title }: NumberFieldProps) {
  const shown = fmt(value / scale)
  // While focused, keep what the user types (e.g. "1." or "") instead of the stored value.
  const [draft, setDraft] = useState<string | null>(null)
  const text = draft ?? shown
  const accepts = (t: string) => {
    const v = Number(t)
    return t.trim() !== '' && Number.isFinite(v) && (!integer || Number.isInteger(v)) && (min === undefined || v >= min)
  }

  return (
    <label className="field" title={title}>
      <span className="field-label">{label}</span>
      <span className="field-input">
        <input
          className={accepts(text) ? '' : 'invalid'}
          inputMode="decimal"
          value={text}
          onFocus={() => setDraft(shown)}
          onBlur={() => setDraft(null)}
          onChange={(ev) => {
            setDraft(ev.target.value)
            if (accepts(ev.target.value)) onChange(Number(ev.target.value) * scale)
          }}
        />
        {unit && <span className="unit">{unit}</span>}
      </span>
    </label>
  )
}

interface SelectFieldProps<T extends string> {
  label: string
  value: T
  options: readonly (T | { value: T; label: string })[]
  onChange: (v: T) => void
}

export function SelectField<T extends string>({ label, value, options, onChange }: SelectFieldProps<T>) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      <select value={value} onChange={(ev) => onChange(ev.target.value as T)}>
        {options.map((o) => {
          const opt = typeof o === 'string' ? { value: o, label: o } : o
          return (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          )
        })}
      </select>
    </label>
  )
}

export function Section({ title, children, actions }: { title: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-header">
        <h2>{title}</h2>
        {actions}
      </header>
      {children}
    </section>
  )
}
