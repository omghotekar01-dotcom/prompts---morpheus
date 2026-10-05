import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Blocks,
  Box,
  Braces,
  BrainCircuit,
  CheckCircle2,
  CircleGauge,
  Code2,
  Cpu,
  Database,
  FileCode2,
  Gauge,
  History,
  KeyRound,
  LayoutDashboard,
  MemoryStick,
  Network,
  Play,
  Radar,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  TimerReset,
  WandSparkles,
  Workflow,
  X,
  XCircle,
  type LucideIcon
} from 'lucide-react'
import {
  askCopilot,
  assessDecisionConfidence,
  compareSearchQuality,
  draftWorkloadFromAccessTrace,
  draftWorkloadWithAI,
  getCalibrationProfiles,
  getCapabilities,
  getDiagnostics,
  getAIProviderStatus,
  getEvidence,
  getEvents,
  getRunDetail,
  getRuns,
  hasSessionApiKey,
  getStateSummary,
  health,
  resolveDecisionWithMeasurement,
  setSessionApiKey,
  synthesize,
  testAIProvider,
  verifyArtifactFull,
  verifyEvidenceLedger,
  type AccessTraceDraftResponse,
  type AIProviderStatus,
  type AIWorkloadDraftResponse,
  type CandidateResult,
  type CapabilityMap,
  type DecisionConfidenceResponse,
  type DecisionResolutionResponse,
  type EvidenceEntry,
  type EvidenceLedgerVerification,
  type EventItem,
  type FullArtifactVerification,
  type RunSummary,
  type SearchQualityReport,
  type SearchStrategy,
  type StateSummary,
  type SynthesisResult,
  type SystemDiagnostics
} from './api'
import './styles.css'
import './evidence.css'
import './functional.css'

const SAMPLE_SPEC = `version: mws-0.1
name: users_demo
record_count: 100000
fields:
  - name: id
    type: uint64
    cardinality: 100000
  - name: age
    type: uint32
    cardinality: 90
  - name: city
    type: string
    cardinality: 400
queries:
  - kind: point_lookup
    field: id
    weight: 0.55
  - kind: range_scan
    field: age
    weight: 0.25
    selectivity: 0.08
  - kind: filter
    field: city
    weight: 0.20
    selectivity: 0.03
constraints:
  memory_mb: 64
  p99_latency_us: 250
  update_rate: 100
objective:
  latency: 1.0
  memory: 0.15
  update: 0.2
  build: 0.05`


const WORKLOAD_PRESETS = [
  {
    id: 'api-session',
    eyebrow: 'READ-HEAVY API',
    title: 'Session & token lookup',
    copy: 'Fast point lookups with a smaller expiry-scan component and a bounded memory budget.',
    spec: `version: mws-0.1
name: api_session_store
record_count: 1000000
fields:
  - name: session_id
    type: string
    cardinality: 1000000
  - name: user_id
    type: uint64
    cardinality: 250000
  - name: expires_at
    type: uint64
    cardinality: 1000000
queries:
  - kind: point_lookup
    field: session_id
    weight: 0.72
  - kind: filter
    field: user_id
    weight: 0.16
    selectivity: 0.00001
  - kind: range_scan
    field: expires_at
    weight: 0.12
    selectivity: 0.02
constraints:
  memory_mb: 256
  p99_latency_us: 120
  update_rate: 500
objective:
  latency: 1.0
  memory: 0.18
  update: 0.25
  build: 0.04`
  },
  {
    id: 'catalog',
    eyebrow: 'MIXED PRODUCT ACCESS',
    title: 'Catalog lookup & filtering',
    copy: 'Balance exact SKU access, category filtering, and price-range exploration under one workload.',
    spec: `version: mws-0.1
name: product_catalog
record_count: 300000
fields:
  - name: sku
    type: string
    cardinality: 300000
  - name: category
    type: string
    cardinality: 1200
  - name: price
    type: uint32
    cardinality: 50000
queries:
  - kind: point_lookup
    field: sku
    weight: 0.45
  - kind: filter
    field: category
    weight: 0.30
    selectivity: 0.01
  - kind: range_scan
    field: price
    weight: 0.25
    selectivity: 0.08
constraints:
  memory_mb: 192
  p99_latency_us: 300
  update_rate: 120
objective:
  latency: 1.0
  memory: 0.22
  update: 0.16
  build: 0.05`
  },
  {
    id: 'events',
    eyebrow: 'EVENT ANALYTICS',
    title: 'Recent-event exploration',
    copy: 'Combine time-window scans, event-type filters, user filters, and exact event retrieval.',
    spec: `version: mws-0.1
name: event_analytics
record_count: 2000000
fields:
  - name: event_id
    type: uint64
    cardinality: 2000000
  - name: user_id
    type: uint64
    cardinality: 400000
  - name: event_type
    type: string
    cardinality: 80
  - name: timestamp
    type: uint64
    cardinality: 2000000
queries:
  - kind: point_lookup
    field: event_id
    weight: 0.15
  - kind: filter
    field: event_type
    weight: 0.35
    selectivity: 0.025
  - kind: range_scan
    field: timestamp
    weight: 0.35
    selectivity: 0.04
  - kind: filter
    field: user_id
    weight: 0.15
    selectivity: 0.00001
constraints:
  memory_mb: 512
  p99_latency_us: 700
  update_rate: 1000
objective:
  latency: 1.0
  memory: 0.12
  update: 0.28
  build: 0.04`
  },
  {
    id: 'measurement-pilot',
    eyebrow: 'LOCAL MEASUREMENT PILOT',
    title: 'Small read-only decision trial',
    copy: 'A bounded workload designed for the local active-measurement gate when modeled finalists are uncertainty-sensitive.',
    spec: `version: mws-0.1
name: local_measurement_pilot
record_count: 12000
fields:
  - name: id
    type: uint64
    cardinality: 12000
  - name: group_id
    type: uint32
    cardinality: 240
queries:
  - kind: point_lookup
    field: id
    weight: 0.75
  - kind: filter
    field: group_id
    weight: 0.25
    selectivity: 0.01
constraints:
  memory_mb: 64
  update_rate: 0
objective:
  latency: 1.0
  memory: 0.0
  update: 0.0
  build: 0.0`
  }
] as const

type WorkloadPreset = (typeof WORKLOAD_PRESETS)[number]

type NavItem = { label: string; icon: LucideIcon; badge?: string }

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  { title: 'WORKSPACE', items: [
    { label: 'Command Center', icon: LayoutDashboard },
    { label: 'Workloads', icon: Braces },
    { label: 'Synthesis Lab', icon: Workflow },
    { label: 'Decision Review', icon: Gauge, badge: 'MEASURE' },
    { label: 'Experiment History', icon: History }
  ] },
  { title: 'MORE', items: [
    { label: 'Engineering', icon: Blocks },
    { label: 'Audit & Evidence', icon: ShieldCheck }
  ] }
]

const ENGINEERING_DESTINATIONS = new Set([
  'Cost Model',
  'Primitive Registry',
  'Search Space',
  'Code Generator',
  'Machine Profiles',
  'MORPHEUS Copilot',
  'Runtime Observatory'
])

const PRIMARY_WORKFLOW_DESTINATIONS = new Set([
  'Command Center',
  'Workloads',
  'Synthesis Lab',
  'Decision Review'
])

const PRIMITIVE_LABELS: Record<string, string> = {
  robin_hood_hash: 'Robin Hood Hash',
  sorted_array: 'Sorted Array',
  ordered_tree: 'Ordered Tree',
  radix_trie: 'Radix Trie',
  bitmap: 'Bitmap Filter',
  csr_graph: 'CSR Graph'
}

function formatNumber(value: number | undefined | null, digits = 2) {
  if (value === undefined || value === null || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function friendlyState(value?: string | null) {
  if (!value) return 'Not available'
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase())
}

function shortHash(value?: string | null, length = 16) {
  if (!value) return '—'
  return value.length > length ? `${value.slice(0, length)}…` : value
}

function App() {
  const [specText, setSpecText] = useState(SAMPLE_SPEC)
  const [result, setResult] = useState<SynthesisResult | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityMap>({})
  const [stateSummary, setStateSummary] = useState<StateSummary | null>(null)
  const [diagnostics, setDiagnostics] = useState<SystemDiagnostics | null>(null)
  const [evidenceEntries, setEvidenceEntries] = useState<EvidenceEntry[]>([])
  const [ledgerVerification, setLedgerVerification] = useState<EvidenceLedgerVerification | null>(null)
  const [backendVersion, setBackendVersion] = useState('—')
  const [activeCalibration, setActiveCalibration] = useState<string | null>(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [running, setRunning] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verification, setVerification] = useState<FullArtifactVerification | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeNav, setActiveNav] = useState('Command Center')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [apiKeyDraft, setApiKeyDraft] = useState('')
  const [apiKeyConfigured, setApiKeyConfigured] = useState(() => hasSessionApiKey())
  const [apiAccessBlocked, setApiAccessBlocked] = useState(false)
  const [candidateView, setCandidateView] = useState<'feasible' | 'all' | 'pareto'>('feasible')
  const [strategy, setStrategy] = useState<SearchStrategy>('auto')
  const [traceText, setTraceText] = useState('')
  const [traceQueryIndex, setTraceQueryIndex] = useState(0)
  const [traceDraft, setTraceDraft] = useState<AccessTraceDraftResponse | null>(null)
  const [traceBusy, setTraceBusy] = useState(false)
  const [aiStatus, setAiStatus] = useState<AIProviderStatus | null>(null)
  const [aiDescription, setAiDescription] = useState('')
  const [aiUseCurrentSpec, setAiUseCurrentSpec] = useState(true)
  const [aiDraft, setAiDraft] = useState<AIWorkloadDraftResponse | null>(null)
  const [aiDraftBusy, setAiDraftBusy] = useState(false)
  const [aiProbeBusy, setAiProbeBusy] = useState(false)
  const [aiProbeMessage, setAiProbeMessage] = useState<string | null>(null)
  const [copilotQuestion, setCopilotQuestion] = useState('Why was this design selected?')
  const [copilotAnswer, setCopilotAnswer] = useState('Run synthesis, then ask MORPHEUS to explain persisted evidence behind the selected design.')
  const [copilotAuthoritative, setCopilotAuthoritative] = useState<string | null>(null)
  const [copilotAiRendered, setCopilotAiRendered] = useState<string | null>(null)
  const [copilotAiFallback, setCopilotAiFallback] = useState<string | null>(null)
  const [copilotBusy, setCopilotBusy] = useState(false)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [historyBusyRunId, setHistoryBusyRunId] = useState<string | null>(null)
  const workspaceOrigin = typeof window !== 'undefined' ? window.location.origin : 'Current browser origin'
  const [searchQuality, setSearchQuality] = useState<SearchQualityReport | null>(null)
  const [searchQualityBusy, setSearchQualityBusy] = useState(false)
  const [decisionConfidence, setDecisionConfidence] = useState<DecisionConfidenceResponse | null>(null)
  const [decisionResolution, setDecisionResolution] = useState<DecisionResolutionResponse | null>(null)
  const [confidenceBusy, setConfidenceBusy] = useState(false)
  const [resolutionBusy, setResolutionBusy] = useState(false)
  const workloadRecordCount = useMemo(() => {
    const match = specText.match(/^record_count:\s*(\d+)/m)
    return match ? Number(match[1]) : null
  }, [specText])
  const workloadQueryKinds = useMemo(
    () => Array.from(specText.matchAll(/^\s*-\s+kind:\s*([A-Za-z_][A-Za-z0-9_]*)/gm), (match) => match[1]),
    [specText]
  )
  const measurementWithinRecordCap = workloadRecordCount !== null && workloadRecordCount <= 25_000

  const refreshControlPlane = async () => {
    setRefreshing(true)
    const results = await Promise.allSettled([
      health(), getEvents(), getRuns(), getCapabilities(), getStateSummary(),
      getCalibrationProfiles(), getDiagnostics(), getEvidence(20), verifyEvidenceLedger(), getAIProviderStatus()
    ])
    const [healthResult, eventResult, runResult, capabilityResult, stateResult, calibrationResult, diagnosticsResult, evidenceResult, ledgerResult, aiStatusResult] = results
    if (healthResult.status === 'fulfilled') {
      setBackendOnline(true)
      setBackendVersion(healthResult.value.version)
    } else {
      setBackendOnline(false)
    }
    const protectedResults = results.slice(1)
    const authBlocked = protectedResults.some((item) => (
      item.status === 'rejected'
      && item.reason instanceof Error
      && item.reason.message.includes('MORPHEUS API key required')
    ))
    setApiAccessBlocked(authBlocked)
    if (eventResult.status === 'fulfilled') setEvents(eventResult.value)
    if (runResult.status === 'fulfilled') setRuns(runResult.value)
    if (capabilityResult.status === 'fulfilled') setCapabilities(capabilityResult.value)
    if (stateResult.status === 'fulfilled') setStateSummary(stateResult.value)
    if (calibrationResult.status === 'fulfilled') setActiveCalibration(calibrationResult.value.active_profile)
    if (diagnosticsResult.status === 'fulfilled') setDiagnostics(diagnosticsResult.value)
    if (evidenceResult.status === 'fulfilled') setEvidenceEntries(evidenceResult.value)
    if (ledgerResult.status === 'fulfilled') setLedgerVerification(ledgerResult.value)
    if (aiStatusResult.status === 'fulfilled') setAiStatus(aiStatusResult.value)
    else if (!authBlocked) setAiStatus(null)
    setRefreshing(false)
  }

  useEffect(() => { void refreshControlPlane() }, [])

  useEffect(() => {
    if (traceQueryIndex >= Math.max(1, workloadQueryKinds.length)) setTraceQueryIndex(0)
  }, [traceQueryIndex, workloadQueryKinds.length])

  useEffect(() => {
    if (!settingsOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setSettingsOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [settingsOpen])

  const saveSessionCredential = () => {
    const normalized = apiKeyDraft.trim()
    if (!normalized) {
      setError('Enter the MORPHEUS API key configured for this control plane.')
      return
    }
    setSessionApiKey(normalized)
    setApiKeyConfigured(true)
    setApiKeyDraft('')
    setApiAccessBlocked(false)
    setError(null)
    void refreshControlPlane()
  }

  const clearSessionCredential = () => {
    setSessionApiKey('')
    setApiKeyConfigured(false)
    setApiKeyDraft('')
    setApiAccessBlocked(false)
    setError(null)
    void refreshControlPlane()
  }

  const navigate = (label: string) => {
    setActiveNav(label)
    setError(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const isNavItemActive = (label: string) => (
    activeNav === label || (label === 'Engineering' && ENGINEERING_DESTINATIONS.has(activeNav))
  )

  const invalidateDecisionState = () => {
    setResult(null)
    setVerification(null)
    setSearchQuality(null)
    setDecisionConfidence(null)
    setDecisionResolution(null)
    setSelectedRunId(null)
    setTraceDraft(null)
    setAiDraft(null)
    setCopilotAuthoritative(null)
    setCopilotAiRendered(null)
    setCopilotAiFallback(null)
    setCopilotAnswer('Choose or create a persisted synthesis run, then ask MORPHEUS to explain the evidence behind it.')
  }

  const editWorkload = (next: string) => {
    setSpecText(next)
    invalidateDecisionState()
    setError(null)
  }

  const changeSearchStrategy = (next: SearchStrategy) => {
    setStrategy(next)
    invalidateDecisionState()
    setError(null)
  }

  const loadWorkloadPreset = (preset: WorkloadPreset) => {
    setSpecText(preset.spec)
    invalidateDecisionState()
    setError(null)
    navigate('Workloads')
  }

  const generateAiWorkloadDraft = async () => {
    if (!aiDescription.trim()) {
      setError('Describe the workload you want MORPHEUS to model.')
      return
    }
    setAiDraftBusy(true)
    setAiDraft(null)
    setError(null)
    try {
      const response = await draftWorkloadWithAI(
        aiDescription.trim(),
        aiUseCurrentSpec ? specText : undefined
      )
      setAiDraft(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setAiDraftBusy(false)
    }
  }

  const applyAiWorkloadDraft = () => {
    if (!aiDraft) return
    editWorkload(aiDraft.draft_spec_text)
    setAiDraft(null)
  }

  const probeAiProvider = async () => {
    setAiProbeBusy(true)
    setAiProbeMessage(null)
    setError(null)
    try {
      const response = await testAIProvider()
      setAiProbeMessage(response.reachable ? 'Provider reachable and JSON contract verified.' : 'Provider did not confirm readiness.')
      await refreshControlPlane()
    } catch (err) {
      setAiProbeMessage(err instanceof Error ? err.message : String(err))
    } finally {
      setAiProbeBusy(false)
    }
  }

  const parseTraceKeys = (): number[] => {
    const tokens = traceText.split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean)
    if (tokens.length < 2) throw new Error('Provide at least two integer keys from one finite access window.')
    if (tokens.length > 100_000) throw new Error('Trace analysis is capped at 100,000 keys in the interactive product flow.')
    const keys = tokens.map((token) => Number(token))
    if (keys.some((value) => !Number.isSafeInteger(value))) {
      throw new Error('Trace input must contain integer keys separated by commas, spaces, semicolons, or new lines.')
    }
    return keys
  }

  const analyzeTraceDraft = async () => {
    if (!workloadQueryKinds.length) {
      setError('The current workload has no query entries to annotate.')
      return
    }
    setTraceBusy(true)
    setError(null)
    try {
      const response = await draftWorkloadFromAccessTrace(specText, traceQueryIndex, parseTraceKeys())
      setTraceDraft(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setTraceDraft(null)
    } finally {
      setTraceBusy(false)
    }
  }

  const loadTraceFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 2_000_000) {
      setError('Trace file is larger than 2 MB. Use a bounded representative window for the interactive assistant.')
      return
    }
    try {
      setTraceText(await file.text())
      setTraceDraft(null)
      setError(null)
    } catch {
      setError('The selected trace file could not be read as text.')
    }
  }

  const applyTraceDraft = () => {
    if (!traceDraft) return
    editWorkload(traceDraft.draft_spec_text)
    setTraceDraft(null)
  }

  const loadWorkloadFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (file.size > 256_000) {
      setError('MWS files are capped at 256 KB in the interactive editor.')
      return
    }
    try {
      editWorkload(await file.text())
      setError(null)
    } catch {
      setError('The selected workload file could not be read as UTF-8 text.')
    }
  }

  const downloadWorkloadSpec = () => {
    const nameMatch = specText.match(/^name:\s*([^\n#]+)/m)
    const safeName = (nameMatch?.[1] ?? 'morpheus-workload')
      .trim()
      .replace(/[^A-Za-z0-9._-]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'morpheus-workload'
    const blob = new Blob([specText], { type: 'text/yaml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${safeName}.mws.yaml`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const explainPersistedRun = (runId: string) => {
    setSelectedRunId(runId)
    setCopilotQuestion(`Explain why run ${runId} selected its winner and what evidence supports that decision.`)
    setCopilotAuthoritative(null)
    setCopilotAiRendered(null)
    setCopilotAiFallback(null)
    setCopilotAnswer(`Persisted run ${runId} is selected. Ask a question to load its evidence-grounded explanation.`)
    navigate('MORPHEUS Copilot')
  }

  const resumePersistedRun = async (runId: string) => {
    setHistoryBusyRunId(runId)
    setError(null)
    try {
      const detail = await getRunDetail(runId)
      setSpecText(detail.spec_text)
      setResult({ ...detail.result, run_id: detail.run_id })
      setVerification(null)
      setSearchQuality(null)
      setDecisionConfidence(null)
      setDecisionResolution(null)
      setTraceDraft(null)
      setSelectedRunId(detail.run_id)
      setCopilotQuestion('Why was this design selected?')
      setCopilotAuthoritative(null)
      setCopilotAiRendered(null)
      setCopilotAiFallback(null)
      setCopilotAnswer(`Persisted run ${detail.run_id} is restored. Ask MORPHEUS to explain its stored evidence if needed.`)
      setStrategy((detail.strategy as SearchStrategy) || 'auto')
      navigate('Synthesis Lab')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setHistoryBusyRunId(null)
    }
  }

  const downloadDecisionBrief = () => {
    if (!result || !winner) {
      setError('Run synthesis first. A decision brief is generated only from a real MORPHEUS result.')
      navigate('Workloads')
      return
    }

    const routes = winner.assignments.map((assignment) => (
      `- ${assignment.query_kind} on ${assignment.field ?? 'workload-wide'} → ${PRIMITIVE_LABELS[assignment.primitive] ?? assignment.primitive}`
    ))
    const search = result.search_summary
    const verificationState = verification
      ? `${verification.success ? 'PASSED' : 'FAILED'} · ${friendlyState(verification.evidence_state)}`
      : 'Not run in this session'

    const brief = [
      '# MORPHEUS Decision Brief',
      '',
      'A workload-to-physical-design decision record generated from the current local MORPHEUS session.',
      '',
      '## Workload identity',
      `- Spec SHA-256: ${result.spec_hash}`,
      `- Persisted run: ${result.run_id ?? 'not available'}`,
      `- Evidence state: ${friendlyState(result.evidence_state)}`,
      '',
      '## Selected physical design',
      `- Candidate: ${winner.id}`,
      `- Selected primitives: ${winner.unique_primitives.map((item) => PRIMITIVE_LABELS[item] ?? item).join(', ')}`,
      `- Objective score: ${formatNumber(winner.score, 6)}`,
      `- Prediction source: ${winner.prediction_source}`,
      `- Model uncertainty: ${formatNumber(winner.uncertainty_ratio * 100, 2)}%`,
      '',
      '### Modeled estimates — not benchmark measurements',
      `- Predicted latency proxy: ${formatNumber(winner.predicted_latency_us, 4)} μs`,
      `- Predicted memory: ${formatNumber(winner.predicted_memory_mb, 3)} MB`,
      `- Predicted update cost: ${formatNumber(winner.predicted_update_us, 4)} μs`,
      `- Predicted build cost: ${formatNumber(winner.predicted_build_ms, 3)} ms`,
      '',
      '### Operation routing',
      ...routes,
      '',
      '## Search record',
      `- Strategy: ${search?.strategy ?? 'not reported'}`,
      `- Evaluated configurations: ${search?.evaluated_configurations ?? 'not reported'}`,
      `- Feasible configurations: ${search?.feasible_configurations ?? 'not reported'}`,
      `- Search truncated: ${search?.truncated == null ? 'not reported' : search.truncated ? 'yes' : 'no'}`,
      '',
      '## Local artifact verification',
      `- Verification: ${verificationState}`,
      `- Compile gate: ${verification ? (verification.compile_gate.success ? 'PASSED' : 'FAILED') : 'not run'}`,
      `- Behavior gate: ${verification ? (verification.behavior_gate.success ? 'PASSED' : 'FAILED') : 'not run'}`,
      '',
      '## Decision confidence',
      `- Heuristic action: ${decisionConfidence?.assessment.action ?? 'not assessed'}`,
      `- Interval-sensitive finalists: ${decisionConfidence?.assessment.ambiguous_candidate_ids.length ?? 'not assessed'}`,
      `- Runner-up score gap: ${decisionConfidence?.assessment.runner_up_score_gap == null ? 'not reported' : formatNumber(decisionConfidence.assessment.runner_up_score_gap, 7)}`,
      '- Confidence intervals are deterministic engineering heuristics, not statistical confidence intervals.',
      '',
      '## Bounded local measurement',
      `- Resolution action: ${decisionResolution?.report.action ?? 'not run'}`,
      `- Modeled winner: ${decisionResolution?.report.modeled_winner_id ?? winner.id}`,
      `- Locally resolved finalist: ${decisionResolution?.report.resolved_winner_id ?? 'not measured'}`,
      `- Empirical selection allowed: ${decisionResolution ? (decisionResolution.report.empirical_selection_allowed ? 'yes' : 'no') : 'not evaluated'}`,
      '- Any measurement is local to the current machine, declared distributions, bounded finalist set and backend execution budget.',
      '',
      '## Truth boundary',
      '- Predicted values are model outputs and must not be presented as target-machine benchmark measurements.',
      '- Local compile and behavioral verification establish only the explicit gates that were run.',
      '- This brief does not authorize production deployment, automatic migration, or automatic traffic switching.',
      '- Benchmark superiority, production reliability, scientific novelty, and patentability require separate evidence.',
      ''
    ].join('\\n')

    const blob = new Blob([brief], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `morpheus-${winner.id.replace(/[^a-zA-Z0-9_-]/g, '_')}-decision-brief.md`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  }

  const run = async () => {
    if (!backendOnline) {
      setError('MORPHEUS backend is offline. Start START-MORPHEUS.bat, then use Retry connection.')
      return
    }
    setRunning(true)
    setError(null)
    setVerification(null)
    setSearchQuality(null)
    setDecisionConfidence(null)
    setDecisionResolution(null)
    try {
      const payload = await synthesize(specText, strategy)
      setResult(payload)
      setSelectedRunId(payload.run_id ?? null)
      setCopilotAnswer(payload.run_id
        ? `Persisted run ${payload.run_id} is selected. Ask why the design won, what is uncertain, or what evidence supports it.`
        : 'This result was not returned with a persisted run identifier, so evidence-grounded Copilot explanation is unavailable.')
      await refreshControlPlane()
      navigate('Synthesis Lab')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  const verify = async () => {
    if (!result?.winner) {
      setError('Run synthesis first. Verification requires a generated winning candidate.')
      navigate('Workloads')
      return
    }
    setVerifying(true)
    setError(null)
    try {
      const payload = await verifyArtifactFull(specText)
      setVerification(payload.verification)
      await refreshControlPlane()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setVerifying(false)
    }
  }

  const compareSearch = async () => {
    if (!backendOnline) {
      setError('Backend is offline. Search-quality evidence cannot be generated without the control plane.')
      return
    }
    setSearchQualityBusy(true)
    setError(null)
    try {
      const response = await compareSearchQuality(specText, 32, 100000)
      setSearchQuality(response.report)
      await refreshControlPlane()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSearchQualityBusy(false)
    }
  }

  const assessConfidence = async () => {
    if (!result?.winner) {
      setError('Run synthesis first. Decision confidence is assessed against a real candidate set.')
      navigate('Workloads')
      return
    }
    setConfidenceBusy(true)
    setError(null)
    try {
      const response = await assessDecisionConfidence(specText, strategy)
      setDecisionConfidence(response)
      setDecisionResolution(null)
      await refreshControlPlane()
      navigate('Decision Review')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setConfidenceBusy(false)
    }
  }

  const resolveWithMeasurement = async () => {
    if (!result?.winner) {
      setError('Run synthesis first. Local measurement can only review a real modeled decision.')
      navigate('Workloads')
      return
    }
    if (!decisionConfidence) {
      setError('Assess decision confidence before running the bounded local measurement gate.')
      navigate('Decision Review')
      return
    }
    if (decisionConfidence.assessment.action !== 'BENCHMARK_MORE') {
      setError('The interval heuristic does not currently call for active measurement. No benchmark was started.')
      navigate('Decision Review')
      return
    }
    if (!measurementWithinRecordCap) {
      setError('Bounded synchronous measurement is capped at 25,000 records. Use the measurement-ready pilot preset or the offline validation campaign.')
      navigate('Decision Review')
      return
    }
    setResolutionBusy(true)
    setError(null)
    try {
      const response = await resolveDecisionWithMeasurement(specText, strategy)
      setDecisionResolution(response)
      await refreshControlPlane()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setResolutionBusy(false)
    }
  }

  const ask = async () => {
    const copilotRunId = selectedRunId ?? result?.run_id ?? null
    if (!copilotRunId) {
      setError('Choose a persisted run from Experiment History or run a workload first.')
      navigate('Experiment History')
      return
    }
    if (!copilotQuestion.trim()) return
    setCopilotBusy(true)
    setError(null)
    try {
      const response = await askCopilot(copilotRunId, copilotQuestion)
      const authoritative = response.authoritative_answer ?? response.answer
      setCopilotAuthoritative(authoritative)
      setCopilotAiRendered(response.ai_rendered_answer ?? null)
      setCopilotAiFallback(response.ai_fallback ?? null)
      setCopilotAnswer(response.ai_rendered_answer ?? authoritative)
      await refreshControlPlane()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setCopilotBusy(false)
    }
  }

  const winner = result?.winner ?? null
  const visibleCandidates = useMemo(() => {
    if (!result) return []
    if (candidateView === 'pareto') return result.pareto_front.slice(0, 20)
    const source = candidateView === 'feasible' ? result.candidates.filter((candidate) => candidate.feasible) : result.candidates
    return source.slice(0, 20)
  }, [candidateView, result])

  const capabilityEntries = Object.entries(capabilities)
  const implementedCapabilities = capabilityEntries.filter(([, value]) => !value.startsWith('NOT_IMPLEMENTED')).length
  const compilerLabel = diagnostics?.toolchain
    ? `${diagnostics.toolchain.kind.toUpperCase()} · ${diagnostics.toolchain.version.split('\n')[0]}`
    : 'No compiler detected'

  const workflowStages = [
    { label: 'Describe', complete: Boolean(result?.winner), destination: 'Workloads' },
    { label: 'Design', complete: Boolean(result?.winner), destination: 'Synthesis Lab' },
    { label: 'Review', complete: Boolean(decisionConfidence), destination: 'Decision Review' },
    { label: 'Verify', complete: Boolean(verification?.success), destination: 'Synthesis Lab' }
  ]
  const workflowCurrentStage = activeNav === 'Workloads'
    ? 'Describe'
    : activeNav === 'Decision Review'
      ? 'Review'
      : activeNav === 'Synthesis Lab'
        ? (decisionConfidence ? 'Verify' : 'Design')
        : null

  const nextAction = (() => {
    if (apiAccessBlocked) {
      return {
        kicker: 'ACCESS REQUIRED',
        title: 'Unlock this guarded MORPHEUS session',
        copy: 'The backend is online, but protected API routes require the control-plane key for this browser tab.',
        label: 'Open access settings',
        disabled: false,
        run: () => setSettingsOpen(true)
      }
    }
    if (!backendOnline) {
      return {
        kicker: 'CONNECTION',
        title: 'Reconnect the local engine',
        copy: 'MORPHEUS cannot synthesize or verify until the backend is reachable.',
        label: refreshing ? 'Checking…' : 'Retry connection',
        disabled: refreshing,
        run: () => void refreshControlPlane()
      }
    }
    if (!result?.winner) {
      return {
        kicker: 'NEXT STEP',
        title: 'Turn this workload into a physical design',
        copy: 'Run synthesis with the current MWS specification. Nothing is benchmarked or deployed by this action.',
        label: running ? 'Synthesizing…' : 'Run synthesis',
        disabled: running,
        run: () => void run()
      }
    }
    if (!decisionConfidence) {
      return {
        kicker: 'NEXT STEP',
        title: 'Check whether the recommendation is uncertainty-sensitive',
        copy: 'Assess interval overlap before treating the modeled winner as a settled engineering decision.',
        label: confidenceBusy ? 'Assessing…' : 'Assess confidence',
        disabled: confidenceBusy,
        run: () => void assessConfidence()
      }
    }
    if (decisionConfidence.assessment.action === 'BENCHMARK_MORE' && !decisionResolution) {
      if (measurementWithinRecordCap) {
        return {
          kicker: 'EVIDENCE GAP',
          title: 'Measure the ambiguous finalists locally',
          copy: 'The model is uncertainty-sensitive. Run the bounded machine-local finalist check before relying on the ranking.',
          label: resolutionBusy ? 'Measuring…' : 'Run bounded measurement',
          disabled: resolutionBusy,
          run: () => void resolveWithMeasurement()
        }
      }
      return {
        kicker: 'EVIDENCE GAP',
        title: 'Review the measurement plan',
        copy: 'This workload exceeds the synchronous measurement cap. MORPHEUS will not pretend it collected evidence that was not measured.',
        label: 'Open Decision Review',
        disabled: false,
        run: () => navigate('Decision Review')
      }
    }
    if (!verification?.success) {
      return {
        kicker: verification ? 'VERIFICATION NEEDS ATTENTION' : 'NEXT STEP',
        title: verification ? 'Re-run the generated artifact gates' : 'Verify the generated C++20 artifact',
        copy: 'Compile and stateful behavior checks are separate from modeled performance and confidence evidence.',
        label: verifying ? 'Running gates…' : verification ? 'Re-run verification' : 'Run verification',
        disabled: verifying,
        run: () => void verify()
      }
    }
    return {
      kicker: 'DECISION RECORD',
      title: 'The local decision record is ready to review',
      copy: 'Export the current evidence-aware brief. This still does not authorize production deployment or claim universal performance.',
      label: 'Download decision brief',
      disabled: false,
      run: downloadDecisionBrief
    }
  })()

  const runSampleButton = (
    <button className="primary-button" onClick={() => void run()} disabled={running}>
      {running ? <><TimerReset size={18} className="spin" /> Synthesizing…</> : <><Play size={18} fill="currentColor" /> Run current workload</>}
    </button>
  )

  const renderWorkspace = () => {
    switch (activeNav) {
      case 'Workloads':
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Workloads" copy="Describe the access pattern directly, or use a bounded real trace to draft one query's distribution before synthesis." icon={Braces} />
          <article className="panel spec-panel functional-editor">
            <div className="editor-toolbar">
              <div className="chip active">YAML</div><div className="chip">MWS 0.1</div>
              <label className="strategy-control"><span>Search</span><select value={strategy} onChange={(event) => changeSearchStrategy(event.target.value as SearchStrategy)}><option value="auto">Auto</option><option value="exhaustive">Exhaustive</option><option value="beam">Beam</option><option value="greedy">Greedy</option></select></label>
            </div>
            <div className="editor-wrap"><div className="line-rail">{Array.from({ length: specText.split('\n').length }, (_, index) => <span key={index}>{index + 1}</span>)}</div><textarea value={specText} onChange={(event) => editWorkload(event.target.value)} spellCheck={false} aria-label="MORPHEUS workload specification" /></div>
            <div className="action-row">{runSampleButton}<label className="secondary-button file-action">Import MWS<input type="file" accept=".yaml,.yml,.json,.txt,text/yaml,application/json,text/plain" onChange={(event) => void loadWorkloadFile(event)}/></label><button className="secondary-button" onClick={downloadWorkloadSpec}>Export MWS</button><button className="secondary-button" onClick={() => editWorkload(SAMPLE_SPEC)}>Restore example</button></div>
          </article>
          <details className="panel ai-workload-assistant">
            <summary><div><span className="section-kicker">OPTIONAL AI ASSISTANT</span><strong>Draft a validated workload from plain English</strong><small>{aiStatus?.configured ? `${aiStatus.provider} · ${aiStatus.model ?? 'model configured'}` : 'Server-side provider not configured · deterministic editor still works'}</small></div><span>Open assistant</span></summary>
            <div className="ai-workload-body">
              <p className="panel-copy">Describe your records, access patterns, scale and constraints naturally. The model can only propose a draft; MORPHEUS deterministically validates the returned MWS before you can apply it.</p>
              <label className="ai-description"><span>Workload description</span><textarea value={aiDescription} onChange={(event) => { setAiDescription(event.target.value); setAiDraft(null) }} placeholder="Example: I have about 2 million product records. Most traffic is exact SKU lookup, some category filters and price range scans. Reads matter most, memory should stay under 512 MB, and updates are moderate." spellCheck={true}/></label>
              <label className="ai-base-toggle"><input type="checkbox" checked={aiUseCurrentSpec} onChange={(event) => { setAiUseCurrentSpec(event.target.checked); setAiDraft(null) }}/><span>Use the current MWS as a base and preserve it unless my description asks for changes.</span></label>
              <div className="action-row">
                <button className="primary-button" onClick={() => void generateAiWorkloadDraft()} disabled={aiDraftBusy || !aiDescription.trim() || !aiStatus?.configured}>{aiDraftBusy ? 'Drafting & validating…' : 'Generate validated MWS'}</button>
                {!aiStatus?.configured && <button className="secondary-button" onClick={() => setSettingsOpen(true)}>Configure AI</button>}
              </div>
              {aiDraft && <div className="ai-draft-result">
                <div className="trace-result-heading"><div><span>Validated AI draft</span><strong>MWS READY FOR REVIEW</strong><small>Accepted by the deterministic parser after {aiDraft.attempts} bounded provider attempt{aiDraft.attempts === 1 ? '' : 's'}.</small></div><span className="state-pill">{shortHash(aiDraft.resolved_semantic_hash, 12)}</span></div>
                {(aiDraft.provider_assumptions.length > 0 || aiDraft.resolution_assumptions.length > 0) && <div className="ai-assumption-list"><strong>Review these assumptions</strong>{[...aiDraft.provider_assumptions, ...aiDraft.resolution_assumptions].map((item, index) => <span key={`${index}-${item}`}>{item}</span>)}</div>}
                <pre className="ai-draft-preview"><code>{aiDraft.draft_spec_text}</code></pre>
                <div className="truth-callout"><ShieldCheck size={20}/><div><strong>Authority boundary</strong><p>{aiDraft.truth_boundary}</p></div></div>
                <div className="action-row"><button className="primary-button" onClick={applyAiWorkloadDraft}>Apply to editor</button><button className="secondary-button" onClick={() => setAiDraft(null)}>Discard draft</button></div>
              </div>}
            </div>
          </details>
          <details className="panel trace-assistant">
            <summary><div><span className="section-kicker">OPTIONAL REAL-WORLD INPUT</span><strong>Draft distribution semantics from an access trace</strong><small>Finite integer-key traces only · explicit user review required</small></div><span>Open assistant</span></summary>
            <div className="trace-assistant-body">
              <p className="panel-copy">Paste or load a bounded TXT/CSV window of integer keys. MORPHEUS computes descriptive metrics and a deterministic development heuristic, then returns a revised MWS draft for the query you choose. It does not treat the label as a statistical fit test or runtime-control signal.</p>
              <div className="trace-assistant-grid">
                <label><span>Target query</span><select value={traceQueryIndex} onChange={(event) => { setTraceQueryIndex(Number(event.target.value)); setTraceDraft(null) }} disabled={!workloadQueryKinds.length}>{workloadQueryKinds.length ? workloadQueryKinds.map((kind, index) => <option value={index} key={`${kind}-${index}`}>{index + 1}. {kind.replaceAll('_', ' ')}</option>) : <option value={0}>No queries detected</option>}</select></label>
                <label className="trace-file"><span>Load trace file</span><input type="file" accept=".txt,.csv,text/plain,text/csv" onChange={(event) => void loadTraceFile(event)}/><small>Read locally in the browser; maximum 2 MB.</small></label>
              </div>
              <label className="trace-input"><span>Integer access keys</span><textarea value={traceText} onChange={(event) => { setTraceText(event.target.value); setTraceDraft(null) }} placeholder={'42, 42, 7, 42, 18\n42, 7, 42, 91'} spellCheck={false}/></label>
              <div className="action-row"><button className="primary-button" onClick={() => void analyzeTraceDraft()} disabled={traceBusy || !traceText.trim() || !workloadQueryKinds.length}>{traceBusy ? 'Analyzing trace…' : 'Analyze & preview draft'}</button><button className="secondary-button" onClick={() => { setTraceText(''); setTraceDraft(null) }} disabled={!traceText && !traceDraft}>Clear trace</button></div>
              {traceDraft && <div className="trace-result">
                <div className="trace-result-heading"><div><span>Suggested distribution</span><strong>{traceDraft.analysis.suggested_distribution.toUpperCase()}</strong><small>{traceDraft.analysis.suggestion_reason}</small></div><span className="state-pill">{traceDraft.analysis.sample_count.toLocaleString()} samples</span></div>
                <div className="metric-grid"><Metric label="Unique keys" value={traceDraft.analysis.unique_keys.toLocaleString()}/><Metric label="Top 10% mass" value={`${formatNumber(traceDraft.analysis.top_10_percent_key_mass * 100, 1)}%`}/><Metric label="Sequential adjacency" value={`${formatNumber(traceDraft.analysis.sequential_adjacent_ratio * 100, 1)}%`}/><Metric label="Entropy" value={formatNumber(traceDraft.analysis.normalized_frequency_entropy, 3)}/></div>
                <div className="truth-callout"><ShieldCheck size={20}/><div><strong>Research boundary</strong><p>{traceDraft.truth_boundary}</p></div></div>
                <div className="action-row"><button className="primary-button" onClick={applyTraceDraft}>Apply draft to workload</button><button className="secondary-button" onClick={() => setTraceDraft(null)}>Keep current workload</button></div>
              </div>}
            </div>
          </details>
        </div>
      case 'Synthesis Lab':
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Synthesis Lab" copy="Inspect the selected design and run the local compile + stateful differential verification gates." icon={Workflow} />
          {!winner ? <ActionEmpty icon={Workflow} title="No synthesis result yet" copy="The lab does not invent placeholder results. Run the current workload first." action={runSampleButton} /> : <>
            <section className="functional-two-col">
              <article className="panel"><SectionHead kicker="SELECTED DESIGN" title={winner.id} badge={result?.evidence_state ?? 'UNKNOWN'} /><div className="metric-card-grid"><MetricCard icon={Gauge} label="Latency" value={`${formatNumber(winner.predicted_latency_us, 3)} μs`} caption="model proxy"/><MetricCard icon={MemoryStick} label="Memory" value={`${formatNumber(winner.predicted_memory_mb)} MB`} caption="model estimate"/><MetricCard icon={CircleGauge} label="Score" value={formatNumber(winner.score, 4)} caption="declared objective"/><MetricCard icon={Activity} label="Uncertainty" value={`${formatNumber(winner.uncertainty_ratio * 100, 1)}%`} caption="model state"/></div></article>
              <article className="panel"><SectionHead kicker="ARTIFACT GATE" title="Full C++20 Verification" badge={verification?.evidence_state ?? 'NOT RUN'} /><p className="panel-copy">Compile and behavior gates remain separate from modeled performance.</p><div className="stacked-actions"><button className="primary-button wide" onClick={() => void verify()} disabled={verifying}>{verifying ? 'Running gates…' : 'Run Full Verification'}</button><button className="secondary-button wide" onClick={() => void assessConfidence()} disabled={confidenceBusy}><Gauge size={18}/>{confidenceBusy ? 'Assessing confidence…' : 'Review decision confidence'}</button><button className="secondary-button wide" onClick={downloadDecisionBrief}><FileCode2 size={18}/> Download decision brief</button></div>{verification && <VerificationCard verification={verification}/>}</article>
            </section>
            <article className="panel"><SectionHead kicker="PHYSICAL PLAN" title="Operation → Primitive Routing" badge={`${winner.assignments.length} ROUTES`} /><ArchitectureGraph winner={winner}/></article>
          </>}
        </div>
      case 'Decision Review':
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Decision Review" copy="Separate modeled recommendation, uncertainty-sensitive finalists and bounded machine-local measurement before anyone treats a design as deployment evidence." icon={Gauge}/>
          {!winner ? <ActionEmpty icon={Gauge} title="No decision to review" copy="Run synthesis first. MORPHEUS will not manufacture confidence or measurement evidence without a real candidate set." action={runSampleButton}/> : <>
            <section className="functional-two-col">
              <article className="panel">
                <SectionHead kicker="MODEL UNCERTAINTY" title="Decision confidence" badge={decisionConfidence?.evidence_state ?? 'NOT ASSESSED'}/>
                <p className="panel-copy">This gate asks whether candidate uncertainty intervals overlap enough to make the modeled winner decision-sensitive. It is an engineering trigger, not a statistical confidence interval.</p>
                <div className="stacked-actions">
                  <button className="primary-button wide" onClick={() => void assessConfidence()} disabled={confidenceBusy}>{confidenceBusy ? 'Assessing…' : 'Assess decision confidence'}</button>
                </div>
                {decisionConfidence && <div className="decision-review-summary">
                  <div className="metric-grid">
                    <Metric label="Heuristic state" value={decisionConfidence.assessment.decision_confident_under_interval_heuristic ? 'STABLE' : 'SENSITIVE'}/>
                    <Metric label="Action" value={friendlyState(decisionConfidence.assessment.action)}/>
                    <Metric label="Ambiguous finalists" value={String(decisionConfidence.assessment.ambiguous_candidate_ids.length)}/>
                    <Metric label="Runner-up gap" value={formatNumber(decisionConfidence.assessment.runner_up_score_gap, 7)}/>
                  </div>
                  <div className="truth-callout"><ShieldCheck size={20}/><div><strong>Interpretation boundary</strong><p>{decisionConfidence.assessment.truth_boundary}</p></div></div>
                </div>}
              </article>
              <article className="panel">
                <SectionHead kicker="ACTIVE MEASUREMENT" title="Bounded local finalist check" badge={decisionResolution?.evidence_state ?? 'NOT RUN'}/>
                <p className="panel-copy">When the model is uncertainty-sensitive, MORPHEUS can compile and execute a small finalist benchmark under strict local limits. It does not turn one machine into a universal performance oracle.</p>
                <div className="measurement-readiness">
                  <span>Declared records</span><strong>{workloadRecordCount == null ? 'Unknown' : workloadRecordCount.toLocaleString()}</strong>
                  <small>{measurementWithinRecordCap ? 'Within the synchronous 25,000-record cap.' : 'Above the synchronous 25,000-record cap; use the measurement-ready pilot preset or offline campaign.'}</small>
                </div>
                <button className="primary-button wide" onClick={() => void resolveWithMeasurement()} disabled={resolutionBusy || decisionConfidence?.assessment.action !== 'BENCHMARK_MORE' || !measurementWithinRecordCap}>{resolutionBusy ? 'Measuring finalists…' : 'Run bounded local measurement'}</button>
                {decisionConfidence && decisionConfidence.assessment.action !== 'BENCHMARK_MORE' && <div className="inline-hint"><CheckCircle2 size={17}/> The current interval heuristic does not request active measurement.</div>}
              </article>
            </section>
            {decisionConfidence && decisionConfidence.assessment.recommended_measurements.length > 0 && <article className="panel">
              <SectionHead kicker="MEASUREMENT PLAN" title="What MORPHEUS wants to measure" badge={`${decisionConfidence.assessment.recommended_measurements.length} TARGETS`}/>
              <div className="decision-target-grid">{decisionConfidence.assessment.recommended_measurements.map((target) => <div className="decision-target" key={`${target.primitive}-${target.operation}`}><div><strong>{PRIMITIVE_LABELS[target.primitive] ?? target.primitive}</strong><span>{target.operation.replaceAll('_', ' ')}</span></div><small>{target.reason}</small><code>{target.candidate_ids.join(' · ')}</code></div>)}</div>
            </article>}
            {decisionResolution && <article className="panel">
              <SectionHead kicker="LOCAL RESULT" title="Measured finalist resolution" badge={decisionResolution.report.evidence_state}/>
              <div className="metric-grid">
                <Metric label="Modeled winner" value={decisionResolution.report.modeled_winner_id ?? '—'}/>
                <Metric label="Resolved finalist" value={decisionResolution.report.resolved_winner_id ?? '—'}/>
                <Metric label="Selection allowed" value={decisionResolution.report.empirical_selection_allowed ? 'YES' : 'NO'}/>
                <Metric label="Action" value={friendlyState(decisionResolution.report.action)}/>
              </div>
              <p className="panel-copy">{decisionResolution.report.empirical_selection_reason}</p>
              <div className="measured-candidate-list">{decisionResolution.report.measured_candidates.map((candidate) => <div className="measured-candidate" key={candidate.candidate_id}><div><strong>{candidate.candidate_id}</strong><span>{candidate.benchmark_success ? 'Local measurement accepted' : 'Measurement unavailable/rejected'}</span></div><div><small>Predicted latency</small><strong>{formatNumber(candidate.predicted_query_latency_us, 4)} μs</strong></div><div><small>Measured weighted latency</small><strong>{candidate.measured_weighted_query_latency_us == null ? '—' : `${formatNumber(candidate.measured_weighted_query_latency_us, 4)} μs`}</strong></div></div>)}</div>
              <div className="truth-callout"><ShieldCheck size={20}/><div><strong>Machine-local evidence only</strong><p>{decisionResolution.report.truth_boundary}</p></div></div>
            </article>}
          </>}
        </div>
      case 'Experiment History':
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Experiment History" copy="Resume a persisted synthesis decision or ask MORPHEUS to explain its stored evidence. Nothing here invents a browser-only run." icon={History}/>
          <article className="panel">
            <SectionHead kicker="RUNS" title="Recent persisted experiments" badge={`${runs.length} SHOWN`}/>
            {runs.length ? <div className="run-list">{runs.map((item) => <div className="run-row history-run-row" key={item.run_id}><div className="history-run-main"><strong>{item.name}</strong><span>{item.strategy} · {friendlyState(item.evidence_state)}</span><code>{item.winner_candidate_id ?? 'no winner'}</code></div><div className="history-run-actions"><button className="secondary-button" onClick={() => void resumePersistedRun(item.run_id)} disabled={historyBusyRunId === item.run_id}>{historyBusyRunId === item.run_id ? 'Restoring…' : 'Resume run'}</button><button className="secondary-button" onClick={() => explainPersistedRun(item.run_id)}>Explain</button></div></div>)}</div> : <ActionEmpty icon={History} title="No persisted runs" copy="Create the first real experiment from Workloads." action={<button className="primary-button" onClick={() => navigate('Workloads')}>Open Workloads</button>}/>}
          </article>
        </div>
      case 'Engineering':
        return <div className="functional-page">
          <PageHead kicker="ADVANCED TOOLS" title="Engineering workspace" copy="Open deeper model, search, code, machine and observability tools only when you need them. The primary workflow stays focused on the decision you are trying to make." icon={Blocks}/>
          <article className="panel">
            <SectionHead kicker="DRILL DOWN" title="Advanced engineering tools" badge="ON DEMAND"/>
            <div className="tool-grid">
              {[
                { label: 'Cost Model', copy: 'Inspect modeled latency, memory, build and update cost.' , icon: CircleGauge },
                { label: 'Primitive Registry', copy: 'See available physical primitive families and current selections.', icon: Blocks },
                { label: 'Search Space', copy: 'Inspect candidates, Pareto results and search-quality evidence.', icon: Search },
                { label: 'Code Generator', copy: 'Review the generated C++20 artifact tied to the current result.', icon: FileCode2 },
                { label: 'Machine Profiles', copy: 'Inspect local compiler, Python and calibration diagnostics.', icon: Cpu },
                { label: 'Runtime Observatory', copy: 'View local control-plane events and persisted state.', icon: Radar },
                { label: 'MORPHEUS Copilot', copy: 'Ask evidence-grounded questions about a persisted run.', icon: BrainCircuit }
              ].map(({ label, copy, icon: Icon }) => <button className="tool-card" key={label} onClick={() => navigate(label)}><Icon size={21}/><div><strong>{label}</strong><small>{copy}</small></div><span>Open →</span></button>)}
            </div>
          </article>
          <article className="panel">
            <SectionHead kicker="SYSTEM TRUTH" title="Capability Matrix" badge={`${implementedCapabilities} IMPLEMENTED`}/>
            <p className="panel-copy">This matrix reports repository capability state. It is an engineering inventory, not a production-readiness or scientific-superiority score.</p>
            <div className="capability-grid">{capabilityEntries.length ? capabilityEntries.map(([name, state]) => <div className={`capability-card ${state.startsWith('NOT_IMPLEMENTED') ? 'muted' : ''}`} key={name}><div>{state.startsWith('NOT_IMPLEMENTED') ? <AlertTriangle size={18}/> : <CheckCircle2 size={18}/>}<strong>{name.replaceAll('_', ' ')}</strong></div><span>{friendlyState(state)}</span></div>) : <p className="panel-copy">Capability data will appear when the backend is online.</p>}</div>
          </article>
        </div>
      case 'Cost Model':
        return <div className="functional-page"><PageHead kicker="ENGINE" title="Cost Model" copy="Predicted values are model outputs. They are not presented as target-machine benchmark measurements." icon={CircleGauge}/>{winner ? <article className="panel"><SectionHead kicker="CURRENT WINNER" title="Predicted cost vector" badge={winner.prediction_source}/><div className="metric-card-grid"><MetricCard icon={Gauge} label="Latency" value={`${formatNumber(winner.predicted_latency_us, 3)} μs`} caption="weighted proxy"/><MetricCard icon={MemoryStick} label="Memory" value={`${formatNumber(winner.predicted_memory_mb)} MB`} caption="model estimate"/><MetricCard icon={TimerReset} label="Build" value={`${formatNumber(winner.predicted_build_ms)} ms`} caption="model estimate"/><MetricCard icon={Activity} label="Update" value={`${formatNumber(winner.predicted_update_us, 3)} μs`} caption="model estimate"/></div></article> : <ActionEmpty icon={CircleGauge} title="No model output yet" copy="Run synthesis to compute a workload-specific cost vector." action={runSampleButton}/>}</div>
      case 'Primitive Registry':
        return <div className="functional-page"><PageHead kicker="ENGINE" title="Primitive Registry" copy="Primitive families currently represented by the synthesis workspace; selected usage appears after a real run." icon={Blocks}/><article className="panel"><div className="primitive-registry">{Object.entries(PRIMITIVE_LABELS).map(([id, label]) => <div className={`registry-card ${winner?.unique_primitives.includes(id) ? 'selected' : ''}`} key={id}><Box size={22}/><div><strong>{label}</strong><code>{id}</code></div><span>{winner?.unique_primitives.includes(id) ? 'SELECTED' : 'AVAILABLE'}</span></div>)}</div></article></div>
      case 'Search Space':
        return <div className="functional-page"><PageHead kicker="ENGINE" title="Search Space" copy="Explore actual candidate output and compare bounded beam search against the exhaustive model oracle." icon={Search}/><article className="panel"><div className="section-head"><div><span className="section-kicker">CANDIDATES</span><h3>Candidate Explorer</h3></div><div className="segmented"><button className={candidateView === 'feasible' ? 'active' : ''} onClick={() => setCandidateView('feasible')}>Feasible</button><button className={candidateView === 'pareto' ? 'active' : ''} onClick={() => setCandidateView('pareto')}>Pareto</button><button className={candidateView === 'all' ? 'active' : ''} onClick={() => setCandidateView('all')}>All</button></div></div><CandidateTable candidates={visibleCandidates} winnerId={winner?.id}/></article><article className="panel"><SectionHead kicker="RESEARCH GATE" title="Beam vs Exhaustive Oracle" badge={searchQuality?.evidence_state ?? 'NOT EVALUATED'}/><p className="panel-copy">Measures search fidelity inside the model search space, not hardware accuracy.</p><button className="secondary-button" onClick={() => void compareSearch()} disabled={searchQualityBusy}>{searchQualityBusy ? 'Comparing…' : 'Compare Search Quality'}</button>{searchQuality && <div className="metric-grid"><Metric label="Winner match" value={searchQuality.winner_matches_oracle ? 'YES' : 'NO'}/><Metric label="Score regret" value={formatNumber(searchQuality.absolute_score_regret, 7)}/><Metric label="Search reduction" value={`${formatNumber(searchQuality.search_reduction_ratio * 100, 1)}%`}/><Metric label="Pareto coverage" value={searchQuality.pareto_id_coverage_ratio == null ? '—' : `${formatNumber(searchQuality.pareto_id_coverage_ratio * 100, 1)}%`}/></div>}</article></div>
      case 'Code Generator':
        return <div className="functional-page"><PageHead kicker="ENGINE" title="Code Generator" copy="Generated C++20 is tied to the current synthesis result and remains subject to explicit verification." icon={FileCode2}/><article className="panel code-panel"><SectionHead kicker="GENERATED ARTIFACT" title="C++20 Preview" badge={result?.generated_code ? 'GENERATED' : 'AWAITING RUN'}/>{result?.generated_code ? <pre className="code-window"><code>{result.generated_code}</code></pre> : <ActionEmpty icon={Code2} title="No generated artifact" copy="Run synthesis first; MORPHEUS will not show fake generated code." action={runSampleButton}/>}</article></div>
      case 'Machine Profiles':
        return <div className="functional-page"><PageHead kicker="ENGINE" title="Machine Profiles" copy="Live local diagnostics and the active calibration identifier reported by the backend." icon={Cpu}/><article className="panel"><SectionHead kicker="LOCAL MACHINE" title="Toolchain Diagnostics" badge={diagnostics?.evidence_state ?? 'UNAVAILABLE'}/><div className="diagnostic-grid"><Diagnostic label="Python" value={diagnostics?.python ?? 'Unavailable'}/><Diagnostic label="Operating system" value={diagnostics?.platform ?? 'Unavailable'}/><Diagnostic label="Architecture" value={diagnostics?.machine ?? 'Unavailable'}/><Diagnostic label="Compiler" value={compilerLabel}/><Diagnostic label="CMake" value={diagnostics?.executables?.cmake ?? 'Not on PATH'} mono/><Diagnostic label="Calibration" value={activeCalibration ?? 'Bootstrap / none active'} mono/></div></article></div>
      case 'MORPHEUS Copilot':
        return <div className="functional-page">
          <PageHead kicker="EVIDENCE ASSISTANT" title="Explain a persisted decision" copy="Deterministic evidence stays authoritative. When a server-side AI provider is configured, it may improve wording but cannot add evidence or control actions." icon={BrainCircuit}/>
          <article className="panel copilot-panel">
            {(selectedRunId ?? result?.run_id) && <div className="copilot-context"><span>Selected run</span><code>{selectedRunId ?? result?.run_id}</code><button className="secondary-button" onClick={() => navigate('Experiment History')}>Change run</button></div>}
            <div className="copilot-mode-row"><span className={aiStatus?.configured ? 'access-state configured' : 'access-state'}>{aiStatus?.configured ? `AI LANGUAGE · ${aiStatus.provider}` : 'DETERMINISTIC ONLY'}</span>{copilotAiFallback && <small>AI fallback: {copilotAiFallback}</small>}</div>
            <div className="copilot-answer"><BrainCircuit size={26}/><div><span>{copilotAiRendered ? 'AI wording' : 'Evidence answer'}</span><p>{copilotAnswer}</p></div></div>
            {copilotAiRendered && copilotAuthoritative && <details className="copilot-authority"><summary>View authoritative deterministic evidence answer</summary><p>{copilotAuthoritative}</p></details>}
            <div className="copilot-input"><input value={copilotQuestion} onChange={(event) => setCopilotQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void ask() }} placeholder="Ask why this design won, what is uncertain, or what evidence exists…"/><button className="primary-button" onClick={() => void ask()} disabled={copilotBusy}>{copilotBusy ? 'Explaining…' : 'Ask'}</button></div>
            {!(selectedRunId ?? result?.run_id) && <div className="inline-hint"><AlertTriangle size={17}/> Choose a persisted run from Experiment History or run a workload first.</div>}
          </article>
        </div>
      case 'Runtime Observatory':
        return <div className="functional-page"><PageHead kicker="INTELLIGENCE" title="Runtime Observatory" copy="Read-only local control-plane state. Automatic production activation remains outside the supported truth boundary." icon={Radar}/><section className="overview-grid"><OverviewCard label="Control plane" value={backendOnline ? 'ONLINE' : 'OFFLINE'} detail={`Backend v${backendVersion}`} icon={Activity} tone={backendOnline ? 'success' : undefined}/><OverviewCard label="Runs" value={String(stateSummary?.synthesis_runs ?? 0)} detail="persisted" icon={History}/><OverviewCard label="Artifacts" value={String(stateSummary?.artifacts ?? 0)} detail="content-addressed" icon={FileCode2}/><OverviewCard label="Evidence" value={String(stateSummary?.evidence_entries ?? evidenceEntries.length)} detail="ledger entries" icon={ShieldCheck}/></section><article className="panel"><SectionHead kicker="EVENT STREAM" title="Recent control-plane events" badge={`${events.length} EVENTS`}/><EventList events={events}/></article></div>
      case 'Audit & Evidence':
        return <div className="functional-page"><PageHead kicker="INTELLIGENCE" title="Audit & Evidence" copy="Inspect the append-only evidence view and hash-chain verification reported by the backend." icon={ShieldCheck}/><article className="panel"><SectionHead kicker="LEDGER" title="Evidence Integrity" badge={ledgerVerification?.evidence_state ?? 'UNAVAILABLE'}/><div className={`integrity-seal ${ledgerVerification?.valid ? 'good' : ledgerVerification ? 'bad' : ''}`}><ShieldCheck size={34}/><strong>{ledgerVerification?.valid ? 'HASH CHAIN VERIFIED' : ledgerVerification ? 'INTEGRITY FAILURE' : 'NO LEDGER STATUS'}</strong><span>{ledgerVerification ? `${ledgerVerification.entries} linked entries` : 'Backend evidence is unavailable.'}</span><code>{shortHash(ledgerVerification?.head_hash, 30)}</code></div><div className="evidence-mini-list">{evidenceEntries.length ? evidenceEntries.map((item) => <div className="evidence-mini-row" key={item.sequence}><span>#{item.sequence}</span><div><strong>{item.kind.replaceAll('_', ' ')}</strong><small>{item.subject}</small></div><code>{shortHash(item.entry_hash, 12)}</code></div>) : <ActionEmpty icon={Network} title="No evidence entries" copy="Run a control-plane action to create persisted evidence." action={runSampleButton}/>}</div></article></div>
      default:
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Command Center" copy="Turn a real access pattern and resource budget into a physical data-structure plan, generated C++20, and an evidence-backed engineering decision." icon={LayoutDashboard}/>
          <section className="product-story">
            <div className="product-story-copy">
              <span className="section-kicker">THE PROBLEM MORPHEUS SOLVES</span>
              <h3>Stop choosing data structures by habit.</h3>
              <p>Backend teams routinely trade latency, memory, update cost and implementation complexity by intuition. MORPHEUS makes that decision explicit: describe the workload, explore feasible physical designs, generate the artifact, then verify what can actually be verified.</p>
              <div className="product-story-actions">
                <button className="primary-button" onClick={() => navigate('Workloads')}><Braces size={18}/> Describe my workload</button>
                {winner && <button className="secondary-button" onClick={() => navigate('Decision Review')}><Gauge size={18}/> Review confidence</button>}
                {winner && <button className="secondary-button" onClick={downloadDecisionBrief}><FileCode2 size={18}/> Download decision brief</button>}
              </div>
            </div>
            <div className="product-steps" aria-label="MORPHEUS workflow">
              <div className="product-step"><span>01</span><strong>Describe</strong><small>Access mix, scale, constraints and objective.</small></div>
              <div className="product-step"><span>02</span><strong>Design</strong><small>Search feasible physical compositions and routing plans.</small></div>
              <div className="product-step"><span>03</span><strong>Review</strong><small>Check uncertainty and measure bounded finalists when needed.</small></div>
              <div className="product-step"><span>04</span><strong>Verify</strong><small>Compile, behavior-check and export a reviewable decision record.</small></div>
            </div>
          </section>
          <article className="panel preset-launchpad">
            <SectionHead kicker="QUICK START" title="Choose a starting workload" badge="REAL SPECS"/>
            <p className="panel-copy">Use a practical template, then edit the workload so it matches your system. MORPHEUS will never treat a template as production evidence.</p>
            <div className="preset-grid">
              {WORKLOAD_PRESETS.map((preset) => <button className="preset-card" key={preset.id} onClick={() => loadWorkloadPreset(preset)}><span>{preset.eyebrow}</span><strong>{preset.title}</strong><small>{preset.copy}</small><em>Use this workload →</em></button>)}
            </div>
          </article>
          <section className="overview-grid product-overview"><OverviewCard label="Current decision" value={winner?.id ?? 'Not run'} detail={winner ? 'Modeled recommendation' : 'Describe a workload to begin'} icon={Workflow}/><OverviewCard label="Saved runs" value={String(stateSummary?.synthesis_runs ?? 0)} detail="Persisted experiments" icon={History}/><OverviewCard label="Evidence integrity" value={ledgerVerification?.valid ? 'VERIFIED' : ledgerVerification ? 'FAILED' : '—'} detail={ledgerVerification?.valid ? 'Hash chain verified' : 'Check Audit & Evidence'} icon={ShieldCheck} tone={ledgerVerification?.valid ? 'success' : undefined}/><OverviewCard label="Control plane" value={backendOnline ? 'ONLINE' : 'OFFLINE'} detail={backendOnline ? `Backend v${backendVersion}` : 'Connection required'} icon={Activity} tone={backendOnline ? 'success' : undefined}/></section>
          {!backendOnline && <div className="offline-callout"><XCircle size={23}/><div><strong>Backend is offline</strong><p>The frontend cannot populate runs, evidence, diagnostics or execute synthesis until the local API is running.</p></div><button className="primary-button" onClick={() => void refreshControlPlane()} disabled={refreshing}><RefreshCw size={18} className={refreshing ? 'spin' : ''}/> Retry connection</button></div>}
          <section className="functional-two-col"><article className="panel"><SectionHead kicker="START HERE" title="Run a workload" badge={backendOnline ? 'READY' : 'BACKEND REQUIRED'}/><p className="panel-copy">The editor already contains a valid example. Open it, change it if needed, then synthesize.</p><div className="action-row"><button className="primary-button" onClick={() => navigate('Workloads')}><Braces size={18}/> Open Workloads</button>{runSampleButton}</div></article><article className="panel"><SectionHead kicker="CURRENT RESULT" title={winner?.id ?? 'No selected design'} badge={result?.evidence_state ?? 'NO EVIDENCE'}/>{winner ? <div className="metric-grid"><Metric label="Score" value={formatNumber(winner.score, 4)}/><Metric label="Primitives" value={String(winner.unique_primitives.length)}/><Metric label="Routes" value={String(winner.assignments.length)}/><Metric label="Source" value={winner.prediction_source}/></div> : <p className="panel-copy">No fake telemetry is shown. Run synthesis to populate this card.</p>}</article></section>
        </div>
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark" aria-hidden="true"><span/><span/></div><div><strong>MORPHEUS</strong><small>ENGINEERING INTELLIGENCE</small></div></div>
      <div className="nav-scroll">{NAV_GROUPS.map((group) => <div className="nav-group" key={group.title}><div className="nav-heading">{group.title}</div>{group.items.map(({ label, icon: Icon, badge }) => <button key={label} className={`nav-item ${isNavItemActive(label) ? 'active' : ''}`} aria-current={isNavItemActive(label) ? 'page' : undefined} onClick={() => navigate(label)}><Icon size={21} strokeWidth={1.8}/><span>{label}</span>{badge && <em>{badge}</em>}</button>)}</div>)}</div>
      <div className="agent-card"><div className="agent-title"><Sparkles size={19}/> Evidence Copilot <span>LIVE</span></div><p>Explains persisted synthesis evidence without converting predictions into measurements.</p><button className="secondary-button wide" onClick={() => navigate('MORPHEUS Copilot')}><WandSparkles size={18}/> Open Copilot</button></div>
      <button className={`nav-item settings-item ${settingsOpen ? 'active' : ''}`} onClick={() => setSettingsOpen(true)}><Settings size={21}/><span>Settings</span></button>
    </aside>
    <main className="main-area">
      <header className="topbar functional-topbar"><div className="headline"><div className="eyebrow">WORKLOAD-AWARE PHYSICAL DESIGN</div><h1>MORPHEUS <span>{activeNav}</span></h1></div><div className="status-strip"><StatusCell label="Control plane" value={backendOnline ? (apiAccessBlocked ? 'Locked' : 'Online') : 'Offline'} good={backendOnline && !apiAccessBlocked} icon={Activity}/><StatusCell label="Backend" value={backendOnline ? `v${backendVersion}` : 'Unavailable'} icon={KeyRound}/><button className="status-refresh" onClick={() => void refreshControlPlane()} disabled={refreshing} title="Refresh backend state"><RefreshCw size={19} className={refreshing ? 'spin' : ''}/></button></div></header>
      {PRIMARY_WORKFLOW_DESTINATIONS.has(activeNav) && <section className="workflow-guide" aria-label="MORPHEUS decision workflow">
        <div className="workflow-progress">
          {workflowStages.map((stage, index) => <button key={stage.label} className={`workflow-progress-step ${stage.complete ? 'complete' : ''} ${workflowCurrentStage === stage.label ? 'current' : ''}`} onClick={() => navigate(stage.destination)}><span>{stage.complete ? <CheckCircle2 size={15}/> : index + 1}</span><strong>{stage.label}</strong></button>)}
        </div>
        <div className="next-action-card">
          <div><span>{nextAction.kicker}</span><strong>{nextAction.title}</strong><small>{nextAction.copy}</small></div>
          <button className="primary-button" onClick={nextAction.run} disabled={nextAction.disabled}>{nextAction.label}</button>
        </div>
      </section>}
      {error && <div className="error-banner" role="alert"><XCircle size={21}/><div><strong>{backendOnline ? 'Could not complete that action' : 'Backend unavailable'}</strong><span>{error}</span></div>{!backendOnline && <button className="secondary-button" onClick={() => void refreshControlPlane()} disabled={refreshing}>{refreshing ? 'Checking…' : 'Retry'}</button>}<button className="icon-button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={18}/></button></div>}
      {renderWorkspace()}
      <footer className="footer-note prestige-footer"><ShieldCheck size={20}/><span>Modeled predictions, calibration, compile evidence, behavioral verification and runtime state remain separate truth classes. Automatic production activation is not implied by this UI.</span></footer>
    </main>
    {settingsOpen && <div className="settings-backdrop" role="presentation" onMouseDown={() => setSettingsOpen(false)}><section className="settings-sheet" role="dialog" aria-modal="true" aria-label="MORPHEUS settings" onMouseDown={(event) => event.stopPropagation()}><div className="settings-title"><div><span className="section-kicker">LOCAL WORKSPACE</span><h2>Settings & diagnostics</h2></div><button className="icon-button" onClick={() => setSettingsOpen(false)} aria-label="Close settings"><X size={20}/></button></div><div className="session-access-card"><div className="session-access-heading"><div><span className="section-kicker">GUARDED ACCESS</span><strong>Control-plane key</strong><small>{apiKeyConfigured ? 'A key is available to this browser tab.' : 'No key is stored for this browser tab.'}</small></div><span className={apiKeyConfigured ? 'access-state configured' : 'access-state'}>{apiKeyConfigured ? 'SESSION KEY SET' : 'OPTIONAL LOCALLY'}</span></div><label className="session-access-input"><span>API key</span><input type="password" value={apiKeyDraft} onChange={(event) => setApiKeyDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') saveSessionCredential() }} placeholder={apiKeyConfigured ? 'Enter a replacement key' : 'Enter X-Morpheus-Key'} autoComplete="off" spellCheck={false}/></label><div className="settings-actions"><button className="primary-button" onClick={saveSessionCredential} disabled={!apiKeyDraft.trim()}><KeyRound size={17}/> Use for this tab</button>{apiKeyConfigured && <button className="secondary-button" onClick={clearSessionCredential}>Clear session key</button>}</div><p className="session-access-note">Stored only in browser session storage for this tab/session and attached as <code>X-Morpheus-Key</code> to protected API requests. It is never shown back by MORPHEUS or written into project files. A guarded pilot still requires separately managed TLS/identity controls for network exposure.</p></div><div className="ai-settings-card"><div className="session-access-heading"><div><span className="section-kicker">OPTIONAL AI</span><strong>Language & workload drafting provider</strong><small>{aiStatus?.configured ? `${aiStatus.provider} · ${aiStatus.model ?? 'configured model'}` : aiStatus?.configuration_error ?? 'Disabled. MORPHEUS remains fully deterministic without it.'}</small></div><span className={aiStatus?.configured ? 'access-state configured' : 'access-state'}>{aiStatus?.configured ? 'CONFIGURED' : 'OPTIONAL'}</span></div><div className="diagnostic-grid compact"><Diagnostic label="Provider" value={aiStatus?.provider ?? 'disabled'}/><Diagnostic label="Model" value={aiStatus?.model ?? 'Not configured'} mono/><Diagnostic label="Endpoint" value={aiStatus?.base_url ?? 'Server environment'} mono/><Diagnostic label="Authority" value="Language only · no control"/></div><div className="settings-actions"><button className="secondary-button" onClick={() => void probeAiProvider()} disabled={!aiStatus?.configured || aiProbeBusy}>{aiProbeBusy ? 'Testing…' : 'Test AI provider'}</button></div>{aiProbeMessage && <p className="session-access-note">{aiProbeMessage}</p>}<p className="session-access-note">Configure on the server with <code>MORPHEUS_AI_PROVIDER</code>, <code>MORPHEUS_AI_MODEL</code>, <code>MORPHEUS_AI_BASE_URL</code> and optionally <code>MORPHEUS_AI_API_KEY</code>. Provider secrets are never entered in this browser UI.</p></div><div className="diagnostic-grid"><Diagnostic label="Workspace origin" value={workspaceOrigin} mono/><Diagnostic label="API route" value="Current workspace /api route" mono/><Diagnostic label="Backend state" value={backendOnline ? `${apiAccessBlocked ? 'Locked' : 'Online'} · v${backendVersion}` : 'Offline'}/><Diagnostic label="Calibration" value={activeCalibration ?? 'Bootstrap / none active'}/><Diagnostic label="Database" value={stateSummary?.database ?? 'Unavailable'} mono/><Diagnostic label="Artifact store" value={stateSummary?.artifact_store ?? 'Unavailable'} mono/></div><div className="settings-actions"><button className="primary-button" onClick={() => void refreshControlPlane()} disabled={refreshing}><RefreshCw size={18} className={refreshing ? 'spin' : ''}/> Refresh backend</button><button className="secondary-button" onClick={() => { editWorkload(SAMPLE_SPEC); setSettingsOpen(false); navigate('Workloads') }}>Reset example workload</button></div><div className="truth-callout"><ShieldCheck size={21}/><div><strong>Safety boundary</strong><p>This browser credential unlocks the configured API guard only. It does not add multi-user identity, tenancy, TLS, migration authority, traffic switching or production authorization.</p></div></div></section></div>}
  </div>
}

function PageHead({ kicker, title, copy, icon: Icon }: { kicker: string; title: string; copy: string; icon: LucideIcon }) { return <div className="page-head"><div className="page-head-icon"><Icon size={26}/></div><div><span>{kicker}</span><h2>{title}</h2><p>{copy}</p></div></div> }
function StatusCell({ label, value, icon: Icon, good }: { label: string; value: string; icon: LucideIcon; good?: boolean }) { return <div className="status-cell"><Icon size={21}/><div><small>{label}</small><strong className={good ? 'good-text' : ''}>{value}</strong></div></div> }
function OverviewCard({ label, value, detail, icon: Icon, tone }: { label: string; value: string; detail: string; icon: LucideIcon; tone?: 'success' }) { return <div className={`overview-card ${tone === 'success' ? 'overview-success' : ''}`}><div className="overview-icon"><Icon size={23}/></div><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></div> }
function SectionHead({ kicker, title, badge }: { kicker: string; title: string; badge: string }) { return <div className="section-head"><div><span className="section-kicker">{kicker}</span><h3>{title}</h3></div><span className="state-pill">{friendlyState(badge)}</span></div> }
function Metric({ label, value }: { label: string; value: string }) { return <div className="metric"><span>{label}</span><strong>{value}</strong></div> }
function MetricCard({ icon: Icon, label, value, caption }: { icon: LucideIcon; label: string; value: string; caption: string }) { return <div className="metric-card"><div className="metric-icon"><Icon size={21}/></div><span>{label}</span><strong>{value}</strong><small>{caption}</small></div> }
function Diagnostic({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) { return <div className="diagnostic-item"><span>{label}</span><strong className={mono ? 'diagnostic-mono' : ''}>{value}</strong></div> }
function ActionEmpty({ icon: Icon, title, copy, action }: { icon: LucideIcon; title: string; copy: string; action: React.ReactNode }) { return <div className="action-empty"><Icon size={34}/><strong>{title}</strong><p>{copy}</p><div>{action}</div></div> }
function VerificationCard({ verification }: { verification: FullArtifactVerification }) { return <div className={`verification-summary ${verification.success ? 'good' : 'bad'}`}><div><strong>{verification.success ? 'Verification passed' : 'Verification failed'}</strong><span>{friendlyState(verification.evidence_state)}</span></div><div className="metric-grid"><Metric label="Compile" value={verification.compile_gate.success ? 'PASSED' : 'FAILED'}/><Metric label="Behavior" value={verification.behavior_gate.success ? 'PASSED' : 'FAILED'}/><Metric label="Checks" value={String(verification.behavior_gate.checks)}/><Metric label="Header" value={shortHash(verification.header_sha256, 12)}/></div></div> }
function ArchitectureGraph({ winner }: { winner: CandidateResult }) { return <div className="arch-flow"><div className="data-node"><Database size={27}/><strong>WORKLOAD</strong><small>{winner.assignments.length} routes</small></div><div className="primitive-stack">{winner.assignments.map((assignment) => <div className="primitive-row" key={`${assignment.query_index}-${assignment.primitive}`}><div className="primitive-card"><Box size={21}/><div><strong>{PRIMITIVE_LABELS[assignment.primitive] ?? assignment.primitive}</strong><span>{assignment.field ?? 'global'}</span></div></div><div className="route-line"/><div className="query-card"><strong>{assignment.query_kind.replaceAll('_', ' ')}</strong><small>{assignment.field ?? 'workload-wide'}</small></div></div>)}</div></div> }
function CandidateTable({ candidates, winnerId }: { candidates: CandidateResult[]; winnerId?: string }) { if (!candidates.length) return <div className="empty-state"><Search size={34}/><strong>No candidate evidence yet</strong><p>Run synthesis or change the candidate filter.</p></div>; return <div className="table-scroll"><table><thead><tr><th>Candidate</th><th>Structures</th><th>Latency</th><th>Memory</th><th>Score</th><th>State</th></tr></thead><tbody>{candidates.map((candidate) => <tr key={candidate.id} className={candidate.id === winnerId ? 'winner-row' : ''}><td><code>{candidate.id}</code>{candidate.id === winnerId && <span className="winner-tag">WINNER</span>}</td><td><div className="mini-chips">{candidate.unique_primitives.map((item) => <span key={item}>{PRIMITIVE_LABELS[item] ?? item}</span>)}</div></td><td>{formatNumber(candidate.predicted_latency_us, 3)} μs</td><td>{formatNumber(candidate.predicted_memory_mb)} MB</td><td>{formatNumber(candidate.score, 4)}</td><td>{candidate.feasible ? <span className="ok-state"><CheckCircle2 size={16}/> Feasible</span> : <span className="bad-state"><AlertTriangle size={16}/> Rejected</span>}</td></tr>)}</tbody></table></div> }
function EventList({ events }: { events: EventItem[] }) { return events.length ? <div className="event-list">{events.slice(0, 30).map((event) => <div className="event-row" key={`${event.timestamp}-${event.kind}`}><span className="event-time">{new Date(event.timestamp).toLocaleTimeString([], { hour12: false })}</span><span className={`event-mark ${event.kind.includes('failed') || event.kind.includes('rejected') ? 'bad' : ''}`}/><div><strong>{event.kind.replaceAll('_', ' ')}</strong><p>{event.message}</p></div></div>)}</div> : <div className="empty-state"><Activity size={34}/><strong>No events yet</strong><p>Validation, synthesis and verification events appear here after real backend actions.</p></div> }

export default App
