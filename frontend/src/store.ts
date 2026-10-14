import { create } from 'zustand'
import type { Body, Electrode, JobResults, JobStatus, Project, Study, Terminal } from './api/types'
import { defaultProject } from './defaultProject'
import { bodyRect, fullFaceExtent, uniqueId } from './geometry'

interface State {
  project: Project
  job: JobStatus | null
  results: JobResults | null
  /** Results belong to this job (may differ from `job` while a new run is in progress). */
  resultsJobId: string | null

  setProject: (p: Project) => void
  setName: (name: string) => void
  updateBody: (id: string, b: Body) => void
  addBody: () => void
  removeBody: (id: string) => void
  updateElectrode: (id: string, e: Electrode) => void
  addElectrode: () => void
  removeElectrode: (id: string) => void
  updateTerminal: (id: string, t: Terminal) => void
  addTerminal: () => void
  removeTerminal: (id: string) => string | null
  setStudy: (s: Study) => void
  setJob: (j: JobStatus | null) => void
  setResults: (jobId: string, r: JobResults) => void
}

const replace = <T extends { id: string }>(items: T[], id: string, item: T) =>
  items.map((x) => (x.id === id ? item : x))

export const useStore = create<State>((set, get) => ({
  project: defaultProject,
  job: null,
  results: null,
  resultsJobId: null,

  setProject: (project) => set({ project }),
  setName: (name) => set((s) => ({ project: { ...s.project, name } })),

  updateBody: (id, b) => set((s) => ({ project: { ...s.project, bodies: replace(s.project.bodies, id, b) } })),
  addBody: () =>
    set((s) => {
      const p = s.project
      const top = Math.max(0, ...p.bodies.map((b) => bodyRect(b).z1))
      const last = p.bodies[p.bodies.length - 1]
      const radius = last ? bodyRect(last).r1 : 0.0105
      const body: Body = {
        id: uniqueId('body', p.bodies.map((b) => b.id)),
        shape: 'disc',
        params: { radius, thickness: 1e-3, z_offset: top },
        material_id: last?.material_id ?? 'PZT-4',
        poling: { direction: '+z' },
      }
      return { project: { ...p, bodies: [...p.bodies, body] } }
    }),
  removeBody: (id) =>
    set((s) => ({
      project: {
        ...s.project,
        bodies: s.project.bodies.filter((b) => b.id !== id),
        electrodes: s.project.electrodes.filter((e) => e.body_id !== id),
      },
    })),

  updateElectrode: (id, e) =>
    set((s) => ({ project: { ...s.project, electrodes: replace(s.project.electrodes, id, e) } })),
  addElectrode: () =>
    set((s) => {
      const p = s.project
      const body = p.bodies[0]
      if (!body) return {}
      const e: Electrode = {
        id: uniqueId('el', p.electrodes.map((x) => x.id)),
        body_id: body.id,
        surface: 'top',
        extent: fullFaceExtent('top', body),
        terminal_id: p.terminals[0]?.id ?? '',
      }
      return { project: { ...p, electrodes: [...p.electrodes, e] } }
    }),
  removeElectrode: (id) =>
    set((s) => ({ project: { ...s.project, electrodes: s.project.electrodes.filter((e) => e.id !== id) } })),

  updateTerminal: (id, t) =>
    set((s) => ({ project: { ...s.project, terminals: replace(s.project.terminals, id, t) } })),
  addTerminal: () =>
    set((s) => {
      const id = uniqueId('t', s.project.terminals.map((t) => t.id))
      const t: Terminal = { id, name: `Port ${id.slice(1)}`, role: 'port' }
      return { project: { ...s.project, terminals: [...s.project.terminals, t] } }
    }),
  removeTerminal: (id) => {
    const p = get().project
    const used = p.electrodes.filter((e) => e.terminal_id === id).map((e) => e.id)
    if (used.length) return `Terminal is used by electrode(s) ${used.join(', ')}`
    set({
      project: {
        ...p,
        terminals: p.terminals.filter((t) => t.id !== id),
        study: { ...p.study, ports: (p.study.ports ?? []).filter((x) => x !== id) },
      },
    })
    return null
  },

  setStudy: (study) => set((s) => ({ project: { ...s.project, study } })),
  setJob: (job) => set({ job }),
  setResults: (jobId, results) => set({ results, resultsJobId: jobId }),
}))
