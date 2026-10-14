import type { Terminal } from '../api/types'

// Distinct, colour-blind-friendly hues for terminals (ground is always grey).
const PALETTE = ['#d1495b', '#2e86de', '#e69f00', '#009e73', '#8e44ad', '#cc79a7', '#56b4e9']
export const GROUND_COLOR = '#7a7f87'

export function terminalColor(terminals: Terminal[], id: string): string {
  const t = terminals.find((x) => x.id === id)
  if (!t) return GROUND_COLOR
  if (t.role === 'ground') return GROUND_COLOR
  const others = terminals.filter((x) => x.role !== 'ground')
  return PALETTE[others.findIndex((x) => x.id === id) % PALETTE.length]
}
