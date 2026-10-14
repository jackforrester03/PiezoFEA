import type { Example, JobResults, JobStatus, MaterialSummary, Project } from './types'

export interface Health {
  status: string
  cfs_path: string | null
  cfs_ok: boolean
}

export class ApiError extends Error {}

/** Turn a FastAPI error body (string detail or pydantic error list) into readable text. */
function describe(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: (string | number)[]; msg?: string }) => {
        const loc = (d.loc ?? []).filter((p) => p !== 'body').join('.')
        return loc ? `${loc}: ${d.msg}` : d.msg
      })
      .join('\n')
  }
  return `HTTP ${status}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, init)
  if (!resp.ok) {
    let body: unknown = null
    try {
      body = await resp.json()
    } catch {
      // non-JSON error body
    }
    throw new ApiError(describe(body, resp.status))
  }
  return resp.json() as Promise<T>
}

export const api = {
  health: () => request<Health>('/api/health'),
  materials: () => request<MaterialSummary[]>('/api/materials'),
  examples: () => request<Example[]>('/api/examples'),
  jobs: () => request<JobStatus[]>('/api/jobs'),
  job: (id: string) => request<JobStatus>(`/api/jobs/${id}`),
  results: (id: string) => request<JobResults>(`/api/jobs/${id}/results`),
  project: (id: string) => request<Project>(`/api/jobs/${id}/project`),
  submit: (project: Project) =>
    request<JobStatus>('/api/jobs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(project),
    }),
}
