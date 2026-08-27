export type QueryKind =
  | 'point_lookup'
  | 'range_scan'
  | 'filter'
  | 'prefix_search'
  | 'graph_traversal'
  | 'insert'
  | 'update'
  | 'delete'

export interface Assignment {
  query_index: number
  query_kind: QueryKind
  field: string | null
  primitive: string
}

export interface CandidateResult {
  id: string
  assignments: Assignment[]
  unique_primitives: string[]
  predicted_latency_us: number
  predicted_memory_mb: number
  predicted_build_ms: number
  predicted_update_us: number
  score: number
  feasible: boolean
  rejection_reasons: string[]
}

export interface SynthesisResult {
  spec_hash: string
  evidence_state: string
  winner: CandidateResult | null
  candidates: CandidateResult[]
  generated_code: string | null
  explanation: string[]
  warnings: string[]
}

export interface EventItem {
  timestamp: string
  kind: string
  message: string
  payload: Record<string, unknown>
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
  }
  return response.json() as Promise<T>
}

export function synthesize(specText: string): Promise<SynthesisResult> {
  return request<SynthesisResult>('/api/synthesize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec_text: specText })
  })
}

export function getEvents(): Promise<EventItem[]> {
  return request<EventItem[]>('/api/events')
}

export function health(): Promise<{ status: string; service: string; version: string }> {
  return request('/api/health')
}
