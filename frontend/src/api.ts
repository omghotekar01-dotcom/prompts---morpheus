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

export interface HotPathStructureOption {
  id: string
  label: string
  capabilities: QueryKind[]
  caveat: string
}

export interface HotPathDoctorOptions {
  schema: string
  current_structures: HotPathStructureOption[]
  problem: string
  automatic_control_allowed: boolean
}

export interface HotPathDoctorResponse {
  schema: string
  problem: {
    category: string
    summary: string
    why_it_matters?: string
  }
  workload: {
    record_count: number
    query_routes: number
    operation_mix: Record<string, number>
    distribution_mix: Record<string, number>
    field_pressure: Record<string, number>
    dominant_operation: string | null
    dominant_distribution: string | null
    dominant_field: string | null
    mutation_weight_ratio: number
    memory_constraint_mb: number | null
    p99_constraint_us: number | null
    declared_update_rate: number
  }
  current_structure: {
    id: string
    label: string
    supported_weight_ratio: number | null
    unsupported_weight_ratio: number | null
    unsupported_query_indexes: number[]
    unsupported_operations: string[]
    assessment: string
    caveat: string
    evidence_state: string
  }
  recommendation: null | {
    candidate_id: string
    primitives: Array<{ id: string; label: string; implementation_id: string }>
    routes: Array<{
      query_index: number
      query_kind: QueryKind
      field: string | null
      primitive: string
      primitive_label: string
      implementation_id: string
    }>
    predicted_latency_us: number
    predicted_memory_mb: number
    predicted_build_ms: number
    predicted_update_us: number
    prediction_source: string
    evidence_state: string
    warnings: string[]
  }
  confidence: DecisionConfidenceAssessment | null
  migration_playbook: Array<{
    step: string
    title: string
    action: string
    gate: string
  }>
  next_gate?: string
  launch_state: string
  automatic_control_allowed?: boolean
  truth_boundary: string
}


export interface DecisionFreshnessPassport {
  schema: string
  passport_sha256: string
  freshness_state:
    | 'CURRENT_FOR_SUPPLIED_WINDOWS'
    | 'REVIEW_REQUIRED_AFTER_DRIFT'
    | 'SUPERSEDED_FOR_SUPPLIED_WINDOWS'
    | 'BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE'
  rollout_disposition:
    | 'NO_CHANGE_REQUIRED_CONTINUE_MONITORING'
    | 'HOLD_AND_REMEASURE_CURRENT_RECOMMENDATION'
    | 'HOLD_PRIOR_DECISION_REVALIDATE_OBSERVED_CANDIDATE'
    | 'DO_NOT_ROLLOUT_RESOLVE_CONSTRAINTS'
  summary: string
  evidence_binding: {
    source_spec_hash: string
    query_index: number
    current_structure: string
    baseline_window_sha256: string
    observed_window_sha256: string
    baseline_sample_count: number
    observed_sample_count: number
    baseline_draft_spec_hash: string
    observed_draft_spec_hash: string
    baseline_winner_candidate_id: string | null
    observed_winner_candidate_id: string | null
    baseline_route_primitive: string | null
    observed_route_primitive: string | null
  }
  change_ticket: {
    freshness_state: string
    rollout_disposition: string
    required_evidence_gates: string[]
    stages: Array<{
      id: string
      title: string
      required: boolean
      action: string
    }>
    stop_conditions: string[]
    rollback_requirements: string[]
    automatic_stage_advance_allowed: boolean
    automatic_cutover_allowed: boolean
  }
  baseline_launch_state: string | null
  observed_launch_state: string | null
  eligible_for_runtime_automatic_control: boolean
  truth_boundary: string
}

export interface RealWorkloadTraceIntakeResponse {
  schema: string
  source_format: 'text' | 'csv' | 'json'
  format_detection_reason: string
  selected_key_field: string | null
  key_selection_reason: string
  sample_count: number
  unique_key_count: number
  rejected_count: number
  rejected_samples: Array<{
    location: string
    value: string
    reason: string
  }>
  input_sha256: string
  normalized_window_sha256: string
  keys: number[]
  eligible_for_runtime_automatic_control: boolean
  truth_boundary: string
}

export interface HotPathWatchResponse {
  schema: string
  source_spec_hash: string
  query_index: number
  query_kind: QueryKind
  query_field: string | null
  current_structure: string
  drift: {
    baseline_samples: number
    observed_samples: number
    baseline_unique_keys: number
    observed_unique_keys: number
    key_frequency_tv_distance: number
    normalized_jensen_shannon_divergence: number
    top_10_percent_key_jaccard: number
    threshold: number
    drifted: boolean
    evidence_state: string
    eligible_for_runtime_automatic_control: boolean
    truth_boundary: string
  }
  baseline: {
    analysis: AccessTraceAnalysis
    draft_spec_hash: string
    draft_spec_text: string
    winner_candidate_id: string | null
    route_primitive: string | null
    doctor: HotPathDoctorResponse
  }
  observed: {
    analysis: AccessTraceAnalysis
    draft_spec_hash: string
    draft_spec_text: string
    winner_candidate_id: string | null
    route_primitive: string | null
    doctor: HotPathDoctorResponse
  }
  decision: {
    action: 'KEEP_AND_MONITOR' | 'REMEASURE_RECOMMENDATION_AFTER_DRIFT' | 'RESYNTHESIZE_MEASURE_VERIFY_SHADOW' | 'BLOCKED_OBSERVED_WORKLOAD_INFEASIBLE'
    severity: 'LOW' | 'MEDIUM' | 'HIGH'
    rationale: string
    candidate_changed: boolean
    route_primitive_changed: boolean
    distribution_label_changed: boolean
    recommended_next_gate: string
  }
  freshness_passport: DecisionFreshnessPassport
  evidence_state: string
  eligible_for_runtime_automatic_control: boolean
  truth_boundary: string
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

export interface RunDetail {
  run_id: string
  spec_hash: string
  name: string
  strategy: string
  evidence_state: string
  winner_candidate_id: string | null
  created_at: string
  spec_text: string
  result: SynthesisResult
  artifacts: Array<Record<string, unknown>>
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

export interface AIProviderStatus {
  schema?: string
  configured: boolean
  provider: string
  base_url: string | null
  model: string | null
  api_key_configured: boolean
  timeout_seconds?: number
  evidence_authority: boolean
  automatic_control_authority: boolean
  configuration_error?: string | null
  mode?: string
  truth_boundary?: string
}

export interface AIWorkloadDraftResponse {
  schema: string
  validated: boolean
  attempts: number
  draft_spec_text: string
  resolved_semantic_hash: string
  provider_assumptions: string[]
  resolution_assumptions: string[]
  provider: AIProviderStatus
  evidence_state: string
  eligible_for_runtime_automatic_control: boolean
  truth_boundary: string
}

export interface AIProviderProbeResult {
  reachable: boolean
  provider: AIProviderStatus
  truth_boundary: string
}

export interface CopilotResult {
  answer: string
  mode: string
  confidence: string
  evidence_refs: string[]
  limitations: string[]
  language_plan?: LanguagePlan
  authoritative_answer?: string
  ai_rendered_answer?: string | null
  ai_provider?: AIProviderStatus | null
  ai_fallback?: string | null
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

export interface AccessTraceAnalysis {
  sample_count: number
  unique_keys: number
  unique_ratio: number
  top_1_percent_key_mass: number
  top_10_percent_key_mass: number
  sequential_adjacent_ratio: number
  normalized_frequency_entropy: number
  zipf_theta_estimate: number | null
  zipf_log_rank_r2: number | null
  suggested_distribution: 'uniform' | 'sequential' | 'hotspot' | 'zipf'
  suggestion_reason: string
  evidence_state: string
  eligible_for_runtime_automatic_control: boolean
  truth_boundary: string
}

export interface AccessTraceDraftResponse {
  schema: string
  source_spec_hash: string
  draft_spec_hash: string
  query_index: number
  query_kind: QueryKind
  query_field: string | null
  analysis: AccessTraceAnalysis
  applied_distribution: {
    kind: string
    zipf_theta?: number
    hotspot_fraction?: number
    hotspot_probability?: number
  }
  draft_spec_text: string
  evidence_state: string
  eligible_for_runtime_automatic_control: boolean
  truth_boundary: string
}

export interface CandidateScoreInterval {
  candidate_id: string
  score: number
  uncertainty_ratio: number
  lower: number
  upper: number
  prediction_source: string
}

export interface MeasurementTarget {
  primitive: string
  operation: string
  candidate_ids: string[]
  priority: number
  reason: string
}

export interface DecisionConfidenceAssessment {
  winner_id: string | null
  decision_confident_under_interval_heuristic: boolean
  ambiguous_candidate_ids: string[]
  runner_up_score_gap: number | null
  winner_interval: CandidateScoreInterval | null
  ambiguous_intervals: CandidateScoreInterval[]
  recommended_measurements: MeasurementTarget[]
  action: string
  evidence_state: string
  truth_boundary: string
}

export interface DecisionConfidenceResponse {
  spec_hash: string
  winner_id: string | null
  search_summary: SearchSummary | null
  assessment: DecisionConfidenceAssessment
  evidence_state: string
}

export interface MeasuredCandidateDecision {
  candidate_id: string
  modeled_score: number
  predicted_query_latency_us: number
  measured_weighted_query_latency_us: number | null
  benchmark_success: boolean
  benchmark_evidence_state: string
  configuration_ir_hash: string
  validation_evidence_state: string | null
  failure_reason: string | null
}

export interface MeasurementResolutionReport {
  modeled_winner_id: string | null
  resolved_winner_id: string | null
  action: string
  confidence_assessment: DecisionConfidenceAssessment
  measured_candidates: MeasuredCandidateDecision[]
  empirical_selection_allowed: boolean
  empirical_selection_reason: string
  evidence_state: string
  truth_boundary: string
}

export interface DecisionResolutionResponse {
  spec_hash: string
  search_summary: SearchSummary | null
  report: MeasurementResolutionReport
  evidence_state: string
  execution_budget: {
    estimated_work_units: number
    max_work_units: number
    max_records: number
    compile_timeout_seconds_per_candidate: number
    run_timeout_seconds_per_candidate: number
  }
  execution_boundary: string
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
const API_KEY_SESSION_KEY = 'morpheus-api-key'

export function getSessionApiKey(): string {
  try {
    return window.sessionStorage.getItem(API_KEY_SESSION_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setSessionApiKey(value: string): void {
  const normalized = value.trim()
  try {
    if (normalized) window.sessionStorage.setItem(API_KEY_SESSION_KEY, normalized)
    else window.sessionStorage.removeItem(API_KEY_SESSION_KEY)
  } finally {
    // A newly supplied credential must never reuse an unauthenticated GET promise.
    inFlightGets.clear()
  }
}

export function hasSessionApiKey(): boolean {
  return getSessionApiKey().length > 0
}

function authenticatedInit(url: string, init?: RequestInit): RequestInit | undefined {
  const apiKey = getSessionApiKey()
  if (!apiKey || !url.startsWith('/api/') || url === '/api/health') return init

  const headers = new Headers(init?.headers)
  headers.set('X-Morpheus-Key', apiKey)
  return { ...(init ?? {}), headers }
}

async function executeRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const authenticated = authenticatedInit(url, init)
  const method = (authenticated?.method ?? 'GET').toUpperCase()
  const controller = method === 'GET' && !authenticated?.signal ? new AbortController() : null
  const effectiveInit: RequestInit | undefined = controller
    ? { ...(authenticated ?? {}), signal: controller.signal }
    : authenticated
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

  // Authentication state is part of GET request identity so credential changes
  // cannot accidentally share an in-flight unauthenticated response.
  const requestIdentity = `${getSessionApiKey() ? 'authenticated' : 'anonymous'}:${url}`
  const existing = inFlightGets.get(requestIdentity) as Promise<T> | undefined
  if (existing) return existing

  const pending = executeRequest<T>(url, init).finally(() => {
    inFlightGets.delete(requestIdentity)
  })
  inFlightGets.set(requestIdentity, pending)
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

export function getAIProviderStatus(): Promise<AIProviderStatus> {
  return request<AIProviderStatus>('/api/v2/ai/status')
}

export function testAIProvider(): Promise<AIProviderProbeResult> {
  return request<AIProviderProbeResult>('/api/v2/ai/test', { method: 'POST' })
}

export function draftWorkloadWithAI(
  description: string,
  baseSpecText?: string
): Promise<AIWorkloadDraftResponse> {
  return request<AIWorkloadDraftResponse>('/api/v2/ai/workload-draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      description,
      base_spec_text: baseSpecText || null
    })
  })
}

export function getHotPathDoctorOptions(): Promise<HotPathDoctorOptions> {
  return request<HotPathDoctorOptions>('/api/v2/doctor/hot-path/options')
}

export function diagnoseHotPath(
  specText: string,
  currentStructure: string,
  strategy: SearchStrategy = 'auto'
): Promise<HotPathDoctorResponse> {
  return request<HotPathDoctorResponse>('/api/v2/doctor/hot-path', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      current_structure: currentStructure,
      strategy
    })
  })
}


export function normalizeRealWorkloadTrace(
  content: string,
  formatHint: 'auto' | 'text' | 'csv' | 'json' = 'auto',
  keyField?: string,
  allowInvalidRows = false
): Promise<RealWorkloadTraceIntakeResponse> {
  return request<RealWorkloadTraceIntakeResponse>('/api/v2/doctor/hot-path/trace-intake', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      format_hint: formatHint,
      key_field: keyField?.trim() || null,
      allow_invalid_rows: allowInvalidRows
    })
  })
}

export function watchHotPath(
  specText: string,
  currentStructure: string,
  queryIndex: number,
  baselineKeys: number[],
  observedKeys: number[],
  strategy: SearchStrategy = 'auto',
  threshold = 0.20
): Promise<HotPathWatchResponse> {
  return request<HotPathWatchResponse>('/api/v2/doctor/hot-path/watch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      current_structure: currentStructure,
      query_index: queryIndex,
      baseline_keys: baselineKeys,
      observed_keys: observedKeys,
      threshold,
      strategy
    })
  })
}

export function draftWorkloadFromAccessTrace(
  specText: string,
  queryIndex: number,
  keys: number[]
): Promise<AccessTraceDraftResponse> {
  return request<AccessTraceDraftResponse>('/api/v2/research/access-trace/apply-draft', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      query_index: queryIndex,
      keys
    })
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

export function assessDecisionConfidence(
  specText: string,
  strategy: SearchStrategy = 'auto'
): Promise<DecisionConfidenceResponse> {
  return request<DecisionConfidenceResponse>('/api/v2/research/decision-confidence', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      strategy,
      interval_scale: 1.0,
      max_recommendations: 8
    })
  })
}

export function resolveDecisionWithMeasurement(
  specText: string,
  strategy: SearchStrategy = 'auto'
): Promise<DecisionResolutionResponse> {
  return request<DecisionResolutionResponse>('/api/v2/research/decision-resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      spec_text: specText,
      strategy,
      interval_scale: 1.0,
      max_candidates_to_measure: 3,
      operations: 1000,
      repetitions: 3,
      warmup: 1
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

export function getRunDetail(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`)
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
