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
  compareSearchQuality,
  getCalibrationProfiles,
  getCapabilities,
  getDiagnostics,
  getEvidence,
  getEvents,
  getRuns,
  getStateSummary,
  health,
  synthesize,
  verifyArtifactFull,
  verifyEvidenceLedger,
  type CandidateResult,
  type CapabilityMap,
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

type NavItem = { label: string; icon: LucideIcon; badge?: string }

const NAV_GROUPS: { title: string; items: NavItem[] }[] = [
  { title: 'WORKSPACE', items: [
    { label: 'Command Center', icon: LayoutDashboard },
    { label: 'Workloads', icon: Braces },
    { label: 'Synthesis Lab', icon: Workflow },
    { label: 'Experiment History', icon: History }
  ] },
  { title: 'ENGINE', items: [
    { label: 'Cost Model', icon: CircleGauge },
    { label: 'Primitive Registry', icon: Blocks },
    { label: 'Search Space', icon: Search },
    { label: 'Code Generator', icon: FileCode2 },
    { label: 'Machine Profiles', icon: Cpu }
  ] },
  { title: 'INTELLIGENCE', items: [
    { label: 'MORPHEUS Copilot', icon: BrainCircuit, badge: 'EVIDENCE' },
    { label: 'Runtime Observatory', icon: Radar },
    { label: 'Audit & Evidence', icon: ShieldCheck }
  ] }
]

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
  const [candidateView, setCandidateView] = useState<'feasible' | 'all' | 'pareto'>('feasible')
  const [strategy, setStrategy] = useState<SearchStrategy>('auto')
  const [copilotQuestion, setCopilotQuestion] = useState('Why was this design selected?')
  const [copilotAnswer, setCopilotAnswer] = useState('Run synthesis, then ask MORPHEUS to explain persisted evidence behind the selected design.')
  const [copilotBusy, setCopilotBusy] = useState(false)
  const [searchQuality, setSearchQuality] = useState<SearchQualityReport | null>(null)
  const [searchQualityBusy, setSearchQualityBusy] = useState(false)

  const refreshControlPlane = async () => {
    setRefreshing(true)
    const results = await Promise.allSettled([
      health(), getEvents(), getRuns(), getCapabilities(), getStateSummary(),
      getCalibrationProfiles(), getDiagnostics(), getEvidence(20), verifyEvidenceLedger()
    ])
    const [healthResult, eventResult, runResult, capabilityResult, stateResult, calibrationResult, diagnosticsResult, evidenceResult, ledgerResult] = results
    if (healthResult.status === 'fulfilled') {
      setBackendOnline(true)
      setBackendVersion(healthResult.value.version)
    } else {
      setBackendOnline(false)
    }
    if (eventResult.status === 'fulfilled') setEvents(eventResult.value)
    if (runResult.status === 'fulfilled') setRuns(runResult.value)
    if (capabilityResult.status === 'fulfilled') setCapabilities(capabilityResult.value)
    if (stateResult.status === 'fulfilled') setStateSummary(stateResult.value)
    if (calibrationResult.status === 'fulfilled') setActiveCalibration(calibrationResult.value.active_profile)
    if (diagnosticsResult.status === 'fulfilled') setDiagnostics(diagnosticsResult.value)
    if (evidenceResult.status === 'fulfilled') setEvidenceEntries(evidenceResult.value)
    if (ledgerResult.status === 'fulfilled') setLedgerVerification(ledgerResult.value)
    setRefreshing(false)
  }

  useEffect(() => { void refreshControlPlane() }, [])

  const navigate = (label: string) => {
    setActiveNav(label)
    setError(null)
    window.scrollTo({ top: 0, behavior: 'smooth' })
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
    try {
      const payload = await synthesize(specText, strategy)
      setResult(payload)
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

  const ask = async () => {
    if (!result?.run_id) {
      setError('Run synthesis first so Copilot has persisted evidence to explain.')
      navigate('Workloads')
      return
    }
    if (!copilotQuestion.trim()) return
    setCopilotBusy(true)
    setError(null)
    try {
      const response = await askCopilot(result.run_id, copilotQuestion)
      setCopilotAnswer(response.answer)
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

  const runSampleButton = (
    <button className="primary-button" onClick={() => void run()} disabled={running}>
      {running ? <><TimerReset size={18} className="spin" /> Synthesizing…</> : <><Play size={18} fill="currentColor" /> Run current workload</>}
    </button>
  )

  const renderWorkspace = () => {
    switch (activeNav) {
      case 'Workloads':
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Workloads" copy="Edit a real MWS workload, select the search strategy, then submit it to the local synthesis engine." icon={Braces} />
          <article className="panel spec-panel functional-editor">
            <div className="editor-toolbar">
              <div className="chip active">YAML</div><div className="chip">MWS 0.1</div>
              <label className="strategy-control"><span>Search</span><select value={strategy} onChange={(event) => setStrategy(event.target.value as SearchStrategy)}><option value="auto">Auto</option><option value="exhaustive">Exhaustive</option><option value="beam">Beam</option><option value="greedy">Greedy</option></select></label>
            </div>
            <div className="editor-wrap"><div className="line-rail">{Array.from({ length: specText.split('\n').length }, (_, index) => <span key={index}>{index + 1}</span>)}</div><textarea value={specText} onChange={(event) => setSpecText(event.target.value)} spellCheck={false} aria-label="MORPHEUS workload specification" /></div>
            <div className="action-row">{runSampleButton}<button className="secondary-button" onClick={() => setSpecText(SAMPLE_SPEC)}>Restore example</button></div>
          </article>
        </div>
      case 'Synthesis Lab':
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Synthesis Lab" copy="Inspect the selected design and run the local compile + stateful differential verification gates." icon={Workflow} />
          {!winner ? <ActionEmpty icon={Workflow} title="No synthesis result yet" copy="The lab does not invent placeholder results. Run the current workload first." action={runSampleButton} /> : <>
            <section className="functional-two-col">
              <article className="panel"><SectionHead kicker="SELECTED DESIGN" title={winner.id} badge={result?.evidence_state ?? 'UNKNOWN'} /><div className="metric-card-grid"><MetricCard icon={Gauge} label="Latency" value={`${formatNumber(winner.predicted_latency_us, 3)} μs`} caption="model proxy"/><MetricCard icon={MemoryStick} label="Memory" value={`${formatNumber(winner.predicted_memory_mb)} MB`} caption="model estimate"/><MetricCard icon={CircleGauge} label="Score" value={formatNumber(winner.score, 4)} caption="declared objective"/><MetricCard icon={Activity} label="Uncertainty" value={`${formatNumber(winner.uncertainty_ratio * 100, 1)}%`} caption="model state"/></div></article>
              <article className="panel"><SectionHead kicker="ARTIFACT GATE" title="Full C++20 Verification" badge={verification?.evidence_state ?? 'NOT RUN'} /><p className="panel-copy">Compile and behavior gates remain separate from modeled performance.</p><button className="primary-button wide" onClick={() => void verify()} disabled={verifying}>{verifying ? 'Running gates…' : 'Run Full Verification'}</button>{verification && <VerificationCard verification={verification}/>}</article>
            </section>
            <article className="panel"><SectionHead kicker="PHYSICAL PLAN" title="Operation → Primitive Routing" badge={`${winner.assignments.length} ROUTES`} /><ArchitectureGraph winner={winner}/></article>
          </>}
        </div>
      case 'Experiment History':
        return <div className="functional-page"><PageHead kicker="WORKSPACE" title="Experiment History" copy="Persisted synthesis runs from the backend, not browser-only demo rows." icon={History}/><article className="panel"><SectionHead kicker="RUNS" title="Recent persisted experiments" badge={`${runs.length} SHOWN`}/>{runs.length ? <div className="run-list">{runs.map((item) => <button className="run-row functional-run" key={item.run_id} onClick={() => { setCopilotQuestion(`Explain run ${item.run_id}`); navigate('MORPHEUS Copilot') }}><div><strong>{item.name}</strong><span>{item.strategy} · {friendlyState(item.evidence_state)}</span></div><code>{item.winner_candidate_id ?? 'no winner'}</code></button>)}</div> : <ActionEmpty icon={History} title="No persisted runs" copy="Create the first real experiment from Workloads." action={<button className="primary-button" onClick={() => navigate('Workloads')}>Open Workloads</button>}/>}</article></div>
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
        return <div className="functional-page"><PageHead kicker="INTELLIGENCE" title="MORPHEUS Copilot" copy="Evidence-grounded explanation over a persisted synthesis run. It does not manufacture measurement evidence." icon={BrainCircuit}/><article className="panel copilot-panel"><div className="copilot-answer"><BrainCircuit size={26}/><p>{copilotAnswer}</p></div><div className="copilot-input"><input value={copilotQuestion} onChange={(event) => setCopilotQuestion(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void ask() }} placeholder="Ask about winner, evidence, constraints…"/><button className="primary-button" onClick={() => void ask()} disabled={copilotBusy}>{copilotBusy ? 'Thinking…' : 'Ask'}</button></div>{!result?.run_id && <div className="inline-hint"><AlertTriangle size={17}/> A persisted synthesis run is required. Clicking Ask will take you to the workload flow.</div>}</article></div>
      case 'Runtime Observatory':
        return <div className="functional-page"><PageHead kicker="INTELLIGENCE" title="Runtime Observatory" copy="Read-only local control-plane state. Automatic production activation remains outside the supported truth boundary." icon={Radar}/><section className="overview-grid"><OverviewCard label="Control plane" value={backendOnline ? 'ONLINE' : 'OFFLINE'} detail={`Backend v${backendVersion}`} icon={Activity} tone={backendOnline ? 'success' : undefined}/><OverviewCard label="Runs" value={String(stateSummary?.synthesis_runs ?? 0)} detail="persisted" icon={History}/><OverviewCard label="Artifacts" value={String(stateSummary?.artifacts ?? 0)} detail="content-addressed" icon={FileCode2}/><OverviewCard label="Evidence" value={String(stateSummary?.evidence_entries ?? evidenceEntries.length)} detail="ledger entries" icon={ShieldCheck}/></section><article className="panel"><SectionHead kicker="EVENT STREAM" title="Recent control-plane events" badge={`${events.length} EVENTS`}/><EventList events={events}/></article></div>
      case 'Audit & Evidence':
        return <div className="functional-page"><PageHead kicker="INTELLIGENCE" title="Audit & Evidence" copy="Inspect the append-only evidence view and hash-chain verification reported by the backend." icon={ShieldCheck}/><article className="panel"><SectionHead kicker="LEDGER" title="Evidence Integrity" badge={ledgerVerification?.evidence_state ?? 'UNAVAILABLE'}/><div className={`integrity-seal ${ledgerVerification?.valid ? 'good' : ledgerVerification ? 'bad' : ''}`}><ShieldCheck size={34}/><strong>{ledgerVerification?.valid ? 'HASH CHAIN VERIFIED' : ledgerVerification ? 'INTEGRITY FAILURE' : 'NO LEDGER STATUS'}</strong><span>{ledgerVerification ? `${ledgerVerification.entries} linked entries` : 'Backend evidence is unavailable.'}</span><code>{shortHash(ledgerVerification?.head_hash, 30)}</code></div><div className="evidence-mini-list">{evidenceEntries.length ? evidenceEntries.map((item) => <div className="evidence-mini-row" key={item.sequence}><span>#{item.sequence}</span><div><strong>{item.kind.replaceAll('_', ' ')}</strong><small>{item.subject}</small></div><code>{shortHash(item.entry_hash, 12)}</code></div>) : <ActionEmpty icon={Network} title="No evidence entries" copy="Run a control-plane action to create persisted evidence." action={runSampleButton}/>}</div></article></div>
      default:
        return <div className="functional-page">
          <PageHead kicker="WORKSPACE" title="Command Center" copy="A functional control surface for workload synthesis, local verification, evidence inspection and research-safe diagnostics." icon={LayoutDashboard}/>
          <section className="overview-grid prestige-overview"><OverviewCard label="Synthesis runs" value={String(stateSummary?.synthesis_runs ?? 0)} detail="Persisted experiments" icon={History}/><OverviewCard label="Artifacts" value={String(stateSummary?.artifacts ?? 0)} detail="Content-addressed store" icon={FileCode2}/><OverviewCard label="Evidence entries" value={String(stateSummary?.evidence_entries ?? evidenceEntries.length)} detail="Hash-linked ledger" icon={ShieldCheck}/><OverviewCard label="Ledger integrity" value={ledgerVerification?.valid ? 'VERIFIED' : ledgerVerification ? 'FAILED' : '—'} detail={shortHash(ledgerVerification?.head_hash)} icon={Network} tone={ledgerVerification?.valid ? 'success' : undefined}/><OverviewCard label="Local Python" value={diagnostics?.python ?? '—'} detail={diagnostics?.system ?? 'Runtime diagnostics'} icon={TerminalSquare}/><OverviewCard label="Capabilities" value={`${implementedCapabilities}/${capabilityEntries.length}`} detail="Live truth matrix" icon={Blocks}/></section>
          {!backendOnline && <div className="offline-callout"><XCircle size={23}/><div><strong>Backend is offline</strong><p>The frontend cannot populate runs, evidence, diagnostics or execute synthesis until the local API is running.</p></div><button className="primary-button" onClick={() => void refreshControlPlane()} disabled={refreshing}><RefreshCw size={18} className={refreshing ? 'spin' : ''}/> Retry connection</button></div>}
          <section className="functional-two-col"><article className="panel"><SectionHead kicker="START HERE" title="Run a workload" badge={backendOnline ? 'READY' : 'BACKEND REQUIRED'}/><p className="panel-copy">The editor already contains a valid example. Open it, change it if needed, then synthesize.</p><div className="action-row"><button className="primary-button" onClick={() => navigate('Workloads')}><Braces size={18}/> Open Workloads</button>{runSampleButton}</div></article><article className="panel"><SectionHead kicker="CURRENT RESULT" title={winner?.id ?? 'No selected design'} badge={result?.evidence_state ?? 'NO EVIDENCE'}/>{winner ? <div className="metric-grid"><Metric label="Score" value={formatNumber(winner.score, 4)}/><Metric label="Primitives" value={String(winner.unique_primitives.length)}/><Metric label="Routes" value={String(winner.assignments.length)}/><Metric label="Source" value={winner.prediction_source}/></div> : <p className="panel-copy">No fake telemetry is shown. Run synthesis to populate this card.</p>}</article></section>
          <article className="panel"><SectionHead kicker="SYSTEM TRUTH" title="Capability Matrix" badge={`${implementedCapabilities} IMPLEMENTED`}/><div className="capability-grid">{capabilityEntries.length ? capabilityEntries.map(([name, state]) => <div className={`capability-card ${state.startsWith('NOT_IMPLEMENTED') ? 'muted' : ''}`} key={name}><div>{state.startsWith('NOT_IMPLEMENTED') ? <AlertTriangle size={18}/> : <CheckCircle2 size={18}/>}<strong>{name.replaceAll('_', ' ')}</strong></div><span>{friendlyState(state)}</span></div>) : <p className="panel-copy">Capability data will appear when the backend is online.</p>}</div></article>
        </div>
    }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark" aria-hidden="true"><span/><span/></div><div><strong>MORPHEUS</strong><small>ENGINEERING INTELLIGENCE</small></div></div>
      <div className="nav-scroll">{NAV_GROUPS.map((group) => <div className="nav-group" key={group.title}><div className="nav-heading">{group.title}</div>{group.items.map(({ label, icon: Icon, badge }) => <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => navigate(label)}><Icon size={21} strokeWidth={1.8}/><span>{label}</span>{badge && <em>{badge}</em>}</button>)}</div>)}</div>
      <div className="agent-card"><div className="agent-title"><Sparkles size={19}/> Evidence Copilot <span>LIVE</span></div><p>Explains persisted synthesis evidence without converting predictions into measurements.</p><button className="secondary-button wide" onClick={() => navigate('MORPHEUS Copilot')}><WandSparkles size={18}/> Open Copilot</button></div>
      <button className={`nav-item settings-item ${settingsOpen ? 'active' : ''}`} onClick={() => setSettingsOpen(true)}><Settings size={21}/><span>Settings</span></button>
    </aside>
    <main className="main-area">
      <header className="topbar functional-topbar"><div className="headline"><div className="eyebrow">WORKLOAD-AWARE DATA STRUCTURE SYNTHESIS · VERIFICATION · EVIDENCE</div><h1>MORPHEUS <span>{activeNav}</span></h1></div><div className="status-strip"><StatusCell label="Control plane" value={backendOnline ? 'Online' : 'Offline'} good={backendOnline} icon={Activity}/><StatusCell label="Backend" value={`v${backendVersion}`} icon={KeyRound}/><button className="status-refresh" onClick={() => void refreshControlPlane()} disabled={refreshing} title="Refresh backend state"><RefreshCw size={19} className={refreshing ? 'spin' : ''}/></button></div></header>
      {error && <div className="error-banner"><XCircle size={21}/><div><strong>Action failed</strong><span>{error}</span></div><button className="icon-button" onClick={() => setError(null)} aria-label="Dismiss error"><X size={18}/></button></div>}
      {renderWorkspace()}
      <footer className="footer-note prestige-footer"><ShieldCheck size={20}/><span>Modeled predictions, calibration, compile evidence, behavioral verification and runtime state remain separate truth classes. Automatic production activation is not implied by this UI.</span></footer>
    </main>
    {settingsOpen && <div className="settings-backdrop" role="presentation" onMouseDown={() => setSettingsOpen(false)}><section className="settings-sheet" role="dialog" aria-modal="true" aria-label="MORPHEUS settings" onMouseDown={(event) => event.stopPropagation()}><div className="settings-title"><div><span className="section-kicker">LOCAL WORKSPACE</span><h2>Settings & diagnostics</h2></div><button className="icon-button" onClick={() => setSettingsOpen(false)} aria-label="Close settings"><X size={20}/></button></div><div className="diagnostic-grid"><Diagnostic label="Frontend" value="http://localhost:5173" mono/><Diagnostic label="API" value="http://localhost:8000" mono/><Diagnostic label="Backend state" value={backendOnline ? `Online · v${backendVersion}` : 'Offline'}/><Diagnostic label="Calibration" value={activeCalibration ?? 'Bootstrap / none active'}/><Diagnostic label="Database" value={stateSummary?.database ?? 'Unavailable'} mono/><Diagnostic label="Artifact store" value={stateSummary?.artifact_store ?? 'Unavailable'} mono/></div><div className="settings-actions"><button className="primary-button" onClick={() => void refreshControlPlane()} disabled={refreshing}><RefreshCw size={18} className={refreshing ? 'spin' : ''}/> Refresh backend</button><button className="secondary-button" onClick={() => { setSpecText(SAMPLE_SPEC); setSettingsOpen(false); navigate('Workloads') }}>Reset example workload</button></div><div className="truth-callout"><ShieldCheck size={21}/><div><strong>Safety boundary</strong><p>This settings view is diagnostic only. It does not enable automatic migration, traffic switching or production activation.</p></div></div></section></div>}
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
