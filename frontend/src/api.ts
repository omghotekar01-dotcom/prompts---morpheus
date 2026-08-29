export type QueryKind =
  | 'point_lookup'
  | 'range_scan'
  | 'filter'
  | 'prefix_search'
  | 'graph_traversal'
  | 'insert'
  | 'update'
  | 'delete'

export type SearchStrategy = 'auto' | 'exhaustive' | 'greedy' | 'beam'

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

export interface CompletionGate {
  id: string
  description: string
  capability: string
  value: string
  passed: boolean
}

export interface CompletionPhase {
  id: string
  name: string
  passed_gates: number
  total_gates: number
  engineering_percent: number
  state: string
  gates: CompletionGate[]
}

export interface EngineeringCompletion {
  schema: string
  passed_gates: number
  total_gates: number
  engineering_percent: number
  phases: CompletionPhase[]
  excluded_outcomes: string[]
  truth_note: string
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
  calibration_profiles?: number
  active_calibration_profile?: string | null
  evidence_entries?: number
  database: string
  artifact_store: string
}

export interface CompileVerification {
  success: boolean
  evidence_state: string
  compiler: string | null
  compiler_kind?: string | null
  compiler_version: string | null
  source_sha256: string
  returncode: number | null
  stdout: string
  stderr: string
  command_policy: string
  limitations: string[]
}

export interface BehaviorVerification {
  success: boolean
  evidence_state: string
  compiler: string | null
  compiler_kind: string | null
  compiler_version: string | null
  source_sha256: string
  driver_sha256: string | null
  compile_returncode: number | null
  run_returncode: number | null
  compile_stdout: string
  compile_stderr: string
  run_stdout: string
  run_stderr: string
  checks: number
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

export interface FullArtifactVerification {
  schema: string
  candidate_id: string
  spec_hash: string
  header_sha256: string | null
  success: boolean
  evidence_state: string
  compile_gate: CompileVerification
  behavior_gate: BehaviorVerification
  truth_boundaries: string[]
}

export interface FullVerifyArtifactResult {
  candidate_id: string
  spec_hash: string
  verification: FullArtifactVerification
  header_artifact: Record<string, unknown>
  verification_manifest: Record<string, unknown>
}

export interface LanguagePlan {
  intent: string
  normalized_question: string
  provider_mode: string
  provider_raw_sha256: string | null
  evidence_state: string
}

export interface CopilotResult {
  answer: string
  mode: string
  confidence: string
  evidence_refs: string[]
  limitations: string[]
  language_plan?: LanguagePlan
}

export interface CalibrationProfilesResult {
  active_profile: string | null
  persistence?: string
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

export interface SystemDiagnostics {
  python: string
  python_executable: string
  platform: string
  system: string
  machine: string
  processor: string
  toolchain: { kind: string; executable: string; version: string } | null
  executables: Record<string, string | null>
  morpheus_cxx_override: string | null
  evidence_state: string
}

export interface EvidenceEntry {
  sequence: number
  timestamp: string
  kind: string
  subject: string
  payload: Record<string, unknown>
  previous_hash: string
  entry_hash: string
}

export interface EvidenceLedgerVerification {
  valid: boolean
  entries: number
  head_hash?: string
  failed_sequence?: number
  evidence_state: string
}

export type FeatureMaturity = 'stable' | 'guarded' | 'research' | 'blocked'

export interface FeatureDefinition {
  id: string
  version: string
  maturity: FeatureMaturity
  default_enabled: boolean
  automatic_control_allowed: boolean
  dependencies: string[]
  update_policy: string
  truth_boundary: string
}

export interface FeatureRegistryResult {
  schema: string
  features: FeatureDefinition[]
  truth_boundary: string
}

export interface ApiSchemaContractResult {
  schema: string
  sha256: string
  route_count: number
  contract: {
    schema: string
    paths: Record<string, Record<string, {
      operation_id: string | null
      request_body_required: boolean
      response_codes: string[]
    }>>
  }
  truth_boundary: string
}

const inFlightGets = new Map<string, Promise<unknown>>()
const GET_REQUEST_TIMEOUT_MS = 10_000

async function executeRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  const controller = method === 'GET' && !init?.signal ? new AbortController() : null
  const effectiveInit: RequestInit | undefined = controller
    ? { ...(init ?? {}), signal: controller.signal }
    : init
  const timeout = controller
    ? window.setTimeout(() => controller.abort(), GET_REQUEST_TIMEOUT_MS)
    : undefined

  try {
    const response = await fetch(url, effectiveInit)
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
    }
    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error(`Read-only request timed out after ${GET_REQUEST_TIMEOUT_MS / 1000}s: ${url}`)
    }
    throw error
  } finally {
    if (timeout !== undefined) window.clearTimeout(timeout)
  }
}

function request<T>(url: string, init?: RequestInit): Promise<T> {
  const method = (init?.method ?? 'GET').toUpperCase()
  if (method !== 'GET' || init?.body) return executeRequest<T>(url, init)

  const existing = inFlightGets.get(url) as Promise<T> | undefined
  if (existing) return existing

  const pending = executeRequest<T>(url, init).finally(() => {
    inFlightGets.delete(url)
  })
  inFlightGets.set(url, pending)
  return pending
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

export function verifyArtifactFull(specText: string): Promise<FullVerifyArtifactResult> {
  return request<FullVerifyArtifactResult>('/api/artifact/verify/full', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spec_text: specText })
  })
}

export function askCopilot(runId: string, question: string): Promise<CopilotResult> {
  return request<CopilotResult>('/api/v2/copilot/explain', {
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
  return request<CapabilityMap>('/api/v2/capabilities')
}

export function getEngineeringCompletion(): Promise<EngineeringCompletion> {
  return request<EngineeringCompletion>('/api/v2/completion')
}

export function getFeatureRegistry(): Promise<FeatureRegistryResult> {
  return request<FeatureRegistryResult>('/api/v2/system/features')
}

export function getApiSchemaContract(): Promise<ApiSchemaContractResult> {
  return request<ApiSchemaContractResult>('/api/v2/system/schema-contract')
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

export function getDiagnostics(): Promise<SystemDiagnostics> {
  return request<SystemDiagnostics>('/api/system/diagnostics')
}

export function getEvidence(limit = 20): Promise<EvidenceEntry[]> {
  return request<EvidenceEntry[]>(`/api/evidence?limit=${limit}`)
}

export function verifyEvidenceLedger(): Promise<EvidenceLedgerVerification> {
  return request<EvidenceLedgerVerification>('/api/evidence/verify')
}

export function health(): Promise<HealthResult> {
  return request<HealthResult>('/api/health')
}
