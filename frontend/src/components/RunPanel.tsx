import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Example, JobStatus, Project } from '../api/types'
import { useStore } from '../store'
import { Section } from './fields'

const ACTIVE = ['queued', 'meshing', 'solving', 'postprocessing']

/** Drop study ports that are no longer port terminals (e.g. after a role change). */
function cleaned(p: Project): Project {
  const ports = (p.study.ports ?? []).filter((id) => p.terminals.some((t) => t.id === id && t.role === 'port'))
  return { ...p, study: { ...p.study, ports } }
}

export function RunPanel() {
  const project = useStore((s) => s.project)
  const job = useStore((s) => s.job)
  const setJob = useStore((s) => s.setJob)
  const setResults = useStore((s) => s.setResults)
  const setProject = useStore((s) => s.setProject)
  const setName = useStore((s) => s.setName)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<JobStatus[]>([])
  const [examples, setExamples] = useState<Example[]>([])
  useEffect(() => {
    api.examples().then(setExamples, () => setExamples([]))
  }, [])

  const refreshHistory = useCallback(() => {
    api.jobs().then(setHistory, () => setHistory([]))
  }, [])
  useEffect(refreshHistory, [refreshHistory])

  // Poll the active job until it finishes, then fetch its results.
  useEffect(() => {
    if (!job || !ACTIVE.includes(job.state)) return
    const timer = setInterval(async () => {
      try {
        const s = await api.job(job.job_id)
        setJob(s)
        if (s.state === 'done') {
          setResults(s.job_id, await api.results(s.job_id))
          refreshHistory()
        } else if (s.state === 'failed') {
          refreshHistory()
        }
      } catch (e) {
        setError((e as Error).message)
      }
    }, 1500)
    return () => clearInterval(timer)
  }, [job, setJob, setResults, refreshHistory])

  const run = async () => {
    setError(null)
    try {
      setJob(await api.submit(cleaned(project)))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const load = async (id: string) => {
    setError(null)
    try {
      const [s, p] = await Promise.all([api.job(id), api.project(id)])
      setProject(p)
      setJob(s)
      if (s.state === 'done') setResults(id, await api.results(id))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const busy = !!job && ACTIVE.includes(job.state)

  return (
    <Section title="Run">
      <label className="field">
        <span className="field-label">Project name</span>
        <input value={project.name} onChange={(ev) => setName(ev.target.value)} />
      </label>
      <button className="primary" onClick={run} disabled={busy}>
        {busy ? 'Running…' : 'Run simulation'}
      </button>
      {error && <pre className="error">{error}</pre>}
      {job && <JobInfo job={job} />}
      {examples.length > 0 && (
        <label className="field">
          <span className="field-label">Start from an example (replaces the current project)</span>
          <select
            value=""
            onChange={(ev) => {
              const ex = examples.find((x) => x.id === ev.target.value)
              if (ex) setProject(ex.project)
            }}
          >
            <option value="">Select an example…</option>
            {examples.map((x) => (
              <option key={x.id} value={x.id}>
                {x.project.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {history.length > 0 && (
        <label className="field">
          <span className="field-label">Previous runs (loads project and results)</span>
          <select value="" onChange={(ev) => ev.target.value && load(ev.target.value)}>
            <option value="">Select a run…</option>
            {history.map((h) => (
              <option key={h.job_id} value={h.job_id}>
                {h.job_id.slice(0, 15)} · {h.project_name} · {h.state}
              </option>
            ))}
          </select>
        </label>
      )}
    </Section>
  )
}

function JobInfo({ job }: { job: JobStatus }) {
  return (
    <div className={`job job-${job.state}`}>
      <div>
        <strong>{job.state}</strong> <code>{job.job_id}</code>
      </div>
      {Object.entries(job.runs ?? {}).map(([name, state]) => (
        <div key={name} className="subrun">
          {name}: {state}
        </div>
      ))}
      {job.mesh && (
        <div className="subrun">
          mesh: {String(job.mesh.num_elements)} elements, {String(job.mesh.num_nodes)} nodes, h ={' '}
          {(Number(job.mesh.element_size) * 1e3).toPrecision(3)} mm
        </div>
      )}
      {job.state === 'failed' && <pre className="error">{job.message}</pre>}
      <div className="hint">Files: data/runs/{job.job_id}/</div>
    </div>
  )
}
