export type QueryKind =
  | 'point_lookup'
  | 'range_scan'
  | 'filter'
  | 'prefix_search'
  | 'graph_traversal'
  | 'insert'
  | 'update'
  | 'delete'

export type SearchStrategy = 'auto' | 'exhaustive' | 'beam'

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
  prediction_source: string
  uncertainty_ratio: number
}

export interface SearchSummary {
  strategy: SearchStrategy
  theoretical_configurations: number
  evaluated_configurations: number
  feasible_configurations: number
  truncated: boolean
  max_candidates: number
  beam_width: number | null
}

export interface SynthesisResult {
  spec_hash: string
  evidence_state: string
  winner: CandidateResult | null
  candidates: CandidateResult[]
  generated_code: string | null
  explanation: string[]
  warnings: string[]
  search_summary: SearchSummary | null
  pareto_front: CandidateResult[]
  active_calibration_profile: string | null
  run_id?: string
}

export interface EventItem {
  timestamp: string
  kind: string
  message: string
  payload: Record<string, unknown>
}

export interface HealthResult {
  status: string
  service: string
  version: string
}

export interface CapabilityMap {
  [key: string]: string
}

export interface RunSummary {
  run_id: string
  spec_hash: string
  name: string
  strategy: string
  evidence_state: string
  winner_candidate_id: string | null
  created_at: string
}

export interface StateSummary {
  workloads: number
  synthesis_runs: number
  artifacts: number
  audit_events: number
  database: string
  artifact_store: string
}

export interface CompileVerification {
  success: boolean
  evidence_state: string
  compiler: string | null
  compiler_version: string | null
  source_sha256: string
  returncode: number | null
  stdout: string
  stderr: string
  command_policy: string
  limitations: string[]
}

export interface VerifyArtifactResult {
  candidate_id: string
  spec_hash: string
  verification: CompileVerification
  header_artifact: Record<string, unknown>
  verification_manifest: Record<string, unknown>
}

export interface CopilotResult {
  answer: string
  mode: string
  confidence: string
  evidence_refs: string[]
  limitations: string[]
}

export interface CalibrationProfilesResult {
  active_profile: string | null
  profiles: Array<{
    id: string
    protocol: string
    evidence_state: string
    record_count: number
    operations: number
    machine: Record<string, string>
  }>
}

export interface SearchQualityReport {
  theoretical_configurations: number
  exhaustive_evaluated: number
  beam_evaluated: number
  exhaustive_winner_id: string | null
  beam_winner_id: string | null
  exhaustive_winner_score: number | null
  beam_winner_score: number | null
  winner_matches_oracle: boolean
  absolute_score_regret: number | null
  relative_score_regret: number | null
  search_reduction_ratio: number
  exhaustive_pareto_count: number
  beam_pareto_count: number
  pareto_id_coverage_ratio: number | null
  evidence_state: string
}

export interface SearchQualityResponse {
  spec_hash: string
  report: SearchQualityReport
  truth_note: string
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
  }
  return response.json() as Promise<T>
}

export function synthesize(
  specText: string,
  strategy: SearchStrategy = 'auto',
  maxCandidates = 10000,
  beamWidth = 64
): Promise<SynthesisResult> {
  return request<SynthesisResult>('/api/synthesize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      strategy,
      max_candidates: maxCandidates,
      beam_width: beamWidth
    })
  })
}

export function verifyArtifact(specText: string): Promise<VerifyArtifactResult> {
  return request<VerifyArtifactResult>('/api/artifact/verify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec_text: specText })
  })
}

export function askCopilot(runId: string, question: string): Promise<CopilotResult> {
  return request<CopilotResult>('/api/copilot/explain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, question })
  })
}

export function compareSearchQuality(
  specText: string,
  beamWidth = 32,
  exhaustiveLimit = 100000
): Promise<SearchQualityResponse> {
  return request<SearchQualityResponse>('/api/research/search/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      beam_width: beamWidth,
      exhaustive_limit: exhaustiveLimit
    })
  })
}

export function getEvents(): Promise<EventItem[]> {
  return request<EventItem[]>('/api/events')
}

export function getCapabilities(): Promise<CapabilityMap> {
  return request<CapabilityMap>('/api/capabilities')
}

export function getRuns(limit = 12): Promise<RunSummary[]> {
  return request<RunSummary[]>(`/api/runs?limit=${limit}`)
}

export function getStateSummary(): Promise<StateSummary> {
  return request<StateSummary>('/api/state/summary')
}

export function getCalibrationProfiles(): Promise<CalibrationProfilesResult> {
  return request<CalibrationProfilesResult>('/api/calibration/profiles')
}

export function health(): Promise<HealthResult> {
  return request<HealthResult>('/api/health')
}
