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
  GitBranch,
  History,
  KeyRound,
  LayoutDashboard,
  MemoryStick,
  Network,
  Play,
  Radar,
  Rocket,
  Search,
  ServerCog,
  Settings,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  TimerReset,
  WandSparkles,
  Workflow,
  XCircle,
  type LucideIcon
} from 'lucide-react'
import {
  askCopilot,
  getCalibrationProfiles,
  getCapabilities,
  getEvents,
  getRuns,
  getStateSummary,
  health,
  synthesize,
  verifyArtifact,
  type CandidateResult,
  type CapabilityMap,
  type CompileVerification,
  type EventItem,
  type RunSummary,
  type SearchStrategy,
  type StateSummary,
  type SynthesisResult
} from './api'
import './styles.css'

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
  {
    title: 'WORKSPACE',
    items: [
      { label: 'Command Center', icon: LayoutDashboard },
      { label: 'Workloads', icon: Braces },
      { label: 'Synthesis Lab', icon: Workflow },
      { label: 'Experiment History', icon: History }
    ]
  },
  {
    title: 'ENGINE',
    items: [
      { label: 'Cost Model', icon: CircleGauge },
      { label: 'Primitive Registry', icon: Blocks },
      { label: 'Search Space', icon: Search },
      { label: 'Code Generator', icon: FileCode2 },
      { label: 'Machine Profiles', icon: Cpu }
    ]
  },
  {
    title: 'INTELLIGENCE',
    items: [
      { label: 'MORPHEUS Copilot', icon: BrainCircuit, badge: 'EVIDENCE' },
      { label: 'Runtime Observatory', icon: Radar },
      { label: 'Audit & Evidence', icon: ShieldCheck }
    ]
  }
]

const PRIMITIVE_LABELS: Record<string, string> = {
  robin_hood_hash: 'Robin Hood Hash',
  sorted_array: 'Sorted Array',
  ordered_tree: 'Ordered Tree',
  radix_trie: 'Radix Trie',
  bitmap: 'Bitmap Filter',
  csr_graph: 'CSR Graph'
}

function formatNumber(value: number | undefined, digits = 2) {
  if (value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function friendlyState(value?: string | null) {
  if (!value) return 'Not available'
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase())
}

function App() {
  const [specText, setSpecText] = useState(SAMPLE_SPEC)
  const [result, setResult] = useState<SynthesisResult | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [capabilities, setCapabilities] = useState<CapabilityMap>({})
  const [stateSummary, setStateSummary] = useState<StateSummary | null>(null)
  const [backendVersion, setBackendVersion] = useState('—')
  const [activeCalibration, setActiveCalibration] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verification, setVerification] = useState<CompileVerification | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [activeNav, setActiveNav] = useState('Command Center')
  const [candidateView, setCandidateView] = useState<'feasible' | 'all' | 'pareto'>('feasible')
  const [strategy, setStrategy] = useState<SearchStrategy>('auto')
  const [copilotQuestion, setCopilotQuestion] = useState('Why was this design selected?')
  const [copilotAnswer, setCopilotAnswer] = useState<string>('Run synthesis, then ask MORPHEUS to explain the evidence behind the selected design.')
  const [copilotBusy, setCopilotBusy] = useState(false)

  const refreshControlPlane = async () => {
    const [healthResult, eventResult, runResult, capabilityResult, stateResult, calibrationResult] = await Promise.allSettled([
      health(),
      getEvents(),
      getRuns(),
      getCapabilities(),
      getStateSummary(),
      getCalibrationProfiles()
    ])

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
  }

  useEffect(() => {
    void refreshControlPlane()
  }, [])

  const run = async () => {
    setRunning(true)
    setError(null)
    setVerification(null)
    try {
      const payload = await synthesize(specText, strategy)
      setResult(payload)
      setBackendOnline(true)
      await refreshControlPlane()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  const verify = async () => {
    setVerifying(true)
    setError(null)
    try {
      const payload = await verifyArtifact(specText)
      setVerification(payload.verification)
      await refreshControlPlane()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setVerifying(false)
    }
  }

  const ask = async () => {
    if (!result?.run_id || !copilotQuestion.trim()) return
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
    if (candidateView === 'pareto') return result.pareto_front.slice(0, 12)
    const list = candidateView === 'feasible' ? result.candidates.filter((candidate) => candidate.feasible) : result.candidates
    return list.slice(0, 12)
  }, [candidateView, result])

  const capabilityEntries = Object.entries(capabilities)
  const implementedCapabilities = capabilityEntries.filter(([, value]) => !value.startsWith('NOT_IMPLEMENTED')).length

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true"><span /><span /></div>
          <div>
            <strong>MORPHEUS</strong>
            <small>ENGINEERING INTELLIGENCE</small>
          </div>
        </div>

        <div className="nav-scroll">
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-heading">{group.title}</div>
              {group.items.map(({ label, icon: Icon, badge }) => (
                <button key={label} className={`nav-item ${activeNav === label ? 'active' : ''}`} onClick={() => setActiveNav(label)}>
                  <Icon size={20} strokeWidth={1.8} />
                  <span>{label}</span>
                  {badge && <em>{badge}</em>}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="agent-card">
          <div className="agent-title"><Sparkles size={18} /> Evidence Copilot <span>LIVE</span></div>
          <p>Explains persisted synthesis evidence without converting predictions into measurements.</p>
          <button className="secondary-button wide" onClick={() => setActiveNav('MORPHEUS Copilot')}><WandSparkles size={17} /> Open Copilot</button>
        </div>
        <button className="nav-item settings-item"><Settings size={20} /><span>Settings</span></button>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="headline">
            <div className="eyebrow">WORKLOAD-AWARE DATA STRUCTURE SYNTHESIS PLATFORM</div>
            <h1>MORPHEUS <span>Command Center</span></h1>
            <p>Describe workload intent, search composite physical designs, generate C++20, verify artifacts, preserve experiment provenance, and inspect runtime-control evidence.</p>
          </div>
          <div className="status-strip">
            <StatusCell label="Control plane" value={backendOnline ? 'Online' : 'Offline'} good={backendOnline} icon={Activity} />
            <StatusCell label="Backend" value={`v${backendVersion}`} icon={KeyRound} />
            <StatusCell label="Calibration" value={activeCalibration ?? 'Bootstrap model'} icon={Cpu} />
          </div>
        </header>

        {error && <div className="error-banner"><XCircle size={20} /><div><strong>Action failed</strong><span>{error}</span></div></div>}

        <section className="overview-grid">
          <OverviewCard label="Synthesis runs" value={String(stateSummary?.synthesis_runs ?? 0)} detail="Persisted experiments" icon={History} />
          <OverviewCard label="Artifacts" value={String(stateSummary?.artifacts ?? 0)} detail="Content-addressed store" icon={FileCode2} />
          <OverviewCard label="Audit events" value={String(stateSummary?.audit_events ?? 0)} detail="Evidence trail" icon={ShieldCheck} />
          <OverviewCard label="Capabilities" value={`${implementedCapabilities}/${capabilityEntries.length || 0}`} detail="Implemented or scaffolded" icon={Blocks} />
        </section>

        <section className="hero-grid">
          <article className="panel spec-panel">
            <PanelHeader number="01" title="WORKLOAD INPUT" subtitle="MORPHEUS Workload Specification" icon={Braces} />
            <div className="editor-toolbar">
              <div className="chip active">YAML</div>
              <div className="chip">MWS 0.1</div>
              <label className="strategy-control">
                <span>Search</span>
                <select value={strategy} onChange={(event) => setStrategy(event.target.value as SearchStrategy)}>
                  <option value="auto">Auto</option>
                  <option value="exhaustive">Exhaustive</option>
                  <option value="beam">Beam</option>
                </select>
              </label>
            </div>
            <div className="editor-wrap">
              <div className="line-rail">{Array.from({ length: specText.split('\n').length }, (_, index) => <span key={index}>{index + 1}</span>)}</div>
              <textarea value={specText} onChange={(event) => setSpecText(event.target.value)} spellCheck={false} aria-label="MORPHEUS workload specification" />
            </div>
            <div className="panel-actions">
              <button className="primary-button" onClick={run} disabled={running}>
                {running ? <><TimerReset size={18} className="spin" /> Synthesizing…</> : <><Play size={18} fill="currentColor" /> Synthesize Design</>}
              </button>
              <span className="subtle-copy">Hard constraints remain hard gates.</span>
            </div>
          </article>

          <article className="panel engine-panel">
            <PanelHeader number="02" title="SYNTHESIS ENGINE" subtitle="Search provenance and evidence state" icon={BrainCircuit} />
            <div className="pipeline">
              <PipelineStep icon={ShieldCheck} label="Validate" done={Boolean(result)} active={running} />
              <PipelineStep icon={CircleGauge} label="Model" done={Boolean(result)} active={running} />
              <PipelineStep icon={Search} label="Search" done={Boolean(result)} active={running} />
              <PipelineStep icon={Code2} label="Generate" done={Boolean(result?.generated_code)} active={running} />
            </div>
            <div className="search-surface">
              <div className="section-row"><strong>Search summary</strong><span className="state-pill">{result ? friendlyState(result.evidence_state) : 'Awaiting run'}</span></div>
              <div className="metric-grid compact">
                <Metric label="Strategy" value={result?.search_summary?.strategy ?? strategy} />
                <Metric label="Theoretical" value={formatNumber(result?.search_summary?.theoretical_configurations, 0)} />
                <Metric label="Evaluated" value={formatNumber(result?.search_summary?.evaluated_configurations, 0)} />
                <Metric label="Pareto" value={String(result?.pareto_front.length ?? 0)} />
              </div>
            </div>
            <div className="truth-callout"><Radar size={21} /><div><strong>Evidence boundary</strong><p>{result ? `Prediction source: ${winner?.prediction_source ?? 'none'}. Active calibration: ${result.active_calibration_profile ?? 'none'}.` : 'Predictions are kept separate from target-machine measurements and end-to-end benchmark evidence.'}</p></div></div>
          </article>

          <article className="panel output-panel">
            <PanelHeader number="03" title="SELECTED DESIGN" subtitle="Best feasible candidate under declared objective" icon={Box} />
            {winner ? (
              <div className="winner-content">
                <span className="success-label"><CheckCircle2 size={16} /> FEASIBLE WINNER</span>
                <h2>{winner.id}</h2>
                <p>{winner.unique_primitives.length} physical primitives across {winner.assignments.length} routed operations.</p>
                <div className="winner-list">{winner.unique_primitives.map((primitive) => <div key={primitive}><CheckCircle2 size={16} /><span>{PRIMITIVE_LABELS[primitive] ?? primitive}</span></div>)}</div>
                <div className="winner-facts">
                  <Metric label="Score" value={formatNumber(winner.score, 4)} />
                  <Metric label="Uncertainty" value={`${formatNumber(winner.uncertainty_ratio * 100, 1)}%`} />
                </div>
              </div>
            ) : <EmptyState icon={Box} title="No design selected yet" copy="Run synthesis to render a real candidate instead of placeholder telemetry." />}
          </article>
        </section>

        <section className="mid-grid">
          <article className="panel architecture-panel">
            <SectionHead kicker="PHYSICAL PLAN" title="Operation → Primitive Routing" badge={result?.evidence_state ?? 'NO EVIDENCE'} />
            {winner ? <ArchitectureGraph winner={winner} /> : <EmptyState icon={Workflow} title="Configuration graph is empty" copy="Submit a workload to render the actual routing plan." />}
          </article>

          <article className="panel metrics-panel">
            <SectionHead kicker="PREDICTED PERFORMANCE" title="Cost Vector" badge={winner?.prediction_source ?? 'MODEL OUTPUT'} />
            <div className="metric-card-grid">
              <MetricCard icon={Gauge} label="Latency" value={winner ? `${formatNumber(winner.predicted_latency_us, 3)} μs` : '—'} caption="weighted model proxy" />
              <MetricCard icon={MemoryStick} label="Memory" value={winner ? `${formatNumber(winner.predicted_memory_mb)} MB` : '—'} caption="unique structures" />
              <MetricCard icon={TimerReset} label="Build" value={winner ? `${formatNumber(winner.predicted_build_ms)} ms` : '—'} caption="model estimate" />
              <MetricCard icon={Activity} label="Update" value={winner ? `${formatNumber(winner.predicted_update_us, 3)} μs` : '—'} caption="model estimate" />
            </div>
          </article>
        </section>

        <section className="lower-grid">
          <article className="panel candidate-panel">
            <div className="section-head"><div><span className="section-kicker">SEARCH SPACE</span><h3>Candidate Explorer</h3></div><div className="segmented"><button className={candidateView === 'feasible' ? 'active' : ''} onClick={() => setCandidateView('feasible')}>Feasible</button><button className={candidateView === 'pareto' ? 'active' : ''} onClick={() => setCandidateView('pareto')}>Pareto</button><button className={candidateView === 'all' ? 'active' : ''} onClick={() => setCandidateView('all')}>All</button></div></div>
            <CandidateTable candidates={visibleCandidates} winnerId={winner?.id} />
          </article>

          <article className="panel verify-panel">
            <SectionHead kicker="ARTIFACT GATE" title="C++20 Compile Verification" badge={verification ? friendlyState(verification.evidence_state) : 'NOT RUN'} />
            <div className="verify-content">
              <p>Generate the selected C++20 artifact and compile it with MORPHEUS's fixed-argument local verifier.</p>
              <button className="primary-button wide" onClick={verify} disabled={!winner || verifying}>{verifying ? <><TimerReset size={18} className="spin" /> Verifying…</> : <><ShieldCheck size={18} /> Verify Artifact</>}</button>
              {verification && <div className={`verification-result ${verification.success ? 'good' : 'bad'}`}><strong>{verification.success ? 'Compile gate passed' : 'Compile gate failed'}</strong><span>{verification.compiler_version ?? verification.compiler ?? 'Compiler unavailable'}</span><code>{verification.source_sha256.slice(0, 18)}…</code>{verification.stderr && <pre>{verification.stderr}</pre>}</div>}
            </div>
          </article>
        </section>

        <section className="bottom-grid">
          <article className="panel code-panel">
            <SectionHead kicker="GENERATED ARTIFACT" title="C++20 Preview" badge={result?.generated_code ? 'GENERATED' : 'AWAITING RUN'} />
            <pre className="code-window"><code>{result?.generated_code ?? '// Run synthesis to generate configuration-specific C++20.'}</code></pre>
          </article>

          <article className="panel copilot-panel">
            <SectionHead kicker="INTELLIGENCE" title="Evidence Copilot" badge="DETERMINISTIC" />
            <div className="copilot-body">
              <div className="copilot-answer"><BrainCircuit size={23} /><p>{copilotAnswer}</p></div>
              <div className="copilot-input"><input value={copilotQuestion} onChange={(event) => setCopilotQuestion(event.target.value)} placeholder="Ask about winner, evidence, Pareto, constraints…" /><button className="primary-button" disabled={!result?.run_id || copilotBusy} onClick={ask}>{copilotBusy ? 'Thinking…' : 'Ask'}</button></div>
            </div>
          </article>

          <article className="panel history-panel">
            <SectionHead kicker="EXPERIMENTS" title="Recent Runs" badge={`${runs.length} SHOWN`} />
            <div className="run-list">{runs.length ? runs.slice(0, 8).map((item) => <div className="run-row" key={item.run_id}><div><strong>{item.name}</strong><span>{item.strategy} · {friendlyState(item.evidence_state)}</span></div><code>{item.winner_candidate_id ?? 'no winner'}</code></div>) : <EmptyState icon={History} title="No persisted runs" copy="Synthesis runs appear here after the backend stores them." />}</div>
          </article>
        </section>

        <section className="panel capability-panel">
          <SectionHead kicker="SYSTEM TRUTH" title="Capability Matrix" badge={`${implementedCapabilities} IMPLEMENTED`} />
          <div className="capability-grid">{capabilityEntries.length ? capabilityEntries.map(([name, state]) => <div className={`capability-card ${state.startsWith('NOT_IMPLEMENTED') ? 'muted' : ''}`} key={name}><div><CheckCircle2 size={17} /><strong>{name.replaceAll('_', ' ')}</strong></div><span>{friendlyState(state)}</span></div>) : <EmptyState icon={Blocks} title="Capability data unavailable" copy="Start the backend to load the live capability matrix." />}</div>
        </section>

        <section className="panel event-panel">
          <SectionHead kicker="AUDIT & EVIDENCE" title="Recent Control-Plane Events" badge={`${events.length} EVENTS`} />
          <div className="event-list">{events.length ? events.slice(0, 10).map((event) => <div className="event-row" key={`${event.timestamp}-${event.kind}`}><span className="event-time">{new Date(event.timestamp).toLocaleTimeString([], { hour12: false })}</span><span className={`event-mark ${event.kind.includes('failed') || event.kind.includes('rejected') ? 'bad' : ''}`} /><div><strong>{event.kind.replaceAll('_', ' ')}</strong><p>{event.message}</p></div></div>) : <EmptyState icon={Activity} title="No events yet" copy="Validation, synthesis, verification, and Copilot events appear here." />}</div>
        </section>

        <footer className="footer-note"><ShieldCheck size={18} /><span>MORPHEUS keeps modeled predictions, machine calibration, compile evidence, runtime recommendations, and confirmed state as separate truth classes.</span></footer>
      </main>
    </div>
  )
}

function StatusCell({ label, value, icon: Icon, good }: { label: string; value: string; icon: LucideIcon; good?: boolean }) {
  return <div className="status-cell"><Icon size={20} /><div><small>{label}</small><strong className={good ? 'good-text' : ''}>{value}</strong></div></div>
}

function OverviewCard({ label, value, detail, icon: Icon }: { label: string; value: string; detail: string; icon: LucideIcon }) {
  return <div className="overview-card"><div className="overview-icon"><Icon size={22} /></div><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></div>
}

function PanelHeader({ number, title, subtitle, icon: Icon }: { number: string; title: string; subtitle: string; icon: LucideIcon }) {
  return <div className="panel-header"><div className="step-number">{number}</div><Icon size={22} /><div><h3>{title}</h3><p>{subtitle}</p></div></div>
}

function SectionHead({ kicker, title, badge }: { kicker: string; title: string; badge: string }) {
  return <div className="section-head"><div><span className="section-kicker">{kicker}</span><h3>{title}</h3></div><span className="state-pill">{friendlyState(badge)}</span></div>
}

function PipelineStep({ icon: Icon, label, done, active }: { icon: LucideIcon; label: string; done: boolean; active: boolean }) {
  return <div className={`pipeline-step ${done ? 'done' : active ? 'active' : ''}`}><div className="pipeline-icon">{done ? <CheckCircle2 size={20} /> : <Icon size={20} />}</div><span>{label}</span></div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>
}

function MetricCard({ icon: Icon, label, value, caption }: { icon: LucideIcon; label: string; value: string; caption: string }) {
  return <div className="metric-card"><div className="metric-icon"><Icon size={20} /></div><span>{label}</span><strong>{value}</strong><small>{caption}</small></div>
}

function ArchitectureGraph({ winner }: { winner: CandidateResult }) {
  return <div className="arch-flow"><div className="data-node"><Database size={26} /><strong>WORKLOAD</strong><small>{winner.assignments.length} routes</small></div><div className="primitive-stack">{winner.assignments.map((assignment) => <div className="primitive-row" key={`${assignment.query_index}-${assignment.primitive}`}><div className="primitive-card"><Box size={20} /><div><strong>{PRIMITIVE_LABELS[assignment.primitive] ?? assignment.primitive}</strong><span>{assignment.field ?? 'global'}</span></div></div><div className="route-line" /><div className="query-card"><strong>{assignment.query_kind.replaceAll('_', ' ')}</strong><small>{assignment.field ?? 'workload-wide'}</small></div></div>)}</div></div>
}

function CandidateTable({ candidates, winnerId }: { candidates: CandidateResult[]; winnerId?: string }) {
  if (!candidates.length) return <EmptyState icon={Search} title="No candidate evidence yet" copy="Run synthesis or change the candidate filter." />
  return <div className="table-scroll"><table><thead><tr><th>Candidate</th><th>Structures</th><th>Latency</th><th>Memory</th><th>Uncertainty</th><th>Score</th><th>State</th></tr></thead><tbody>{candidates.map((candidate) => <tr key={candidate.id} className={candidate.id === winnerId ? 'winner-row' : ''}><td><code>{candidate.id}</code>{candidate.id === winnerId && <span className="winner-tag">WINNER</span>}</td><td><div className="mini-chips">{candidate.unique_primitives.map((item) => <span key={item}>{PRIMITIVE_LABELS[item] ?? item}</span>)}</div></td><td>{formatNumber(candidate.predicted_latency_us, 3)} μs</td><td>{formatNumber(candidate.predicted_memory_mb)} MB</td><td>{formatNumber(candidate.uncertainty_ratio * 100, 1)}%</td><td>{formatNumber(candidate.score, 4)}</td><td>{candidate.feasible ? <span className="ok-state"><CheckCircle2 size={15} /> Feasible</span> : <span className="bad-state"><AlertTriangle size={15} /> Rejected</span>}</td></tr>)}</tbody></table></div>
}

function EmptyState({ icon: Icon, title, copy }: { icon: LucideIcon; title: string; copy: string }) {
  return <div className="empty-state"><Icon size={32} /><strong>{title}</strong><p>{copy}</p></div>
}

export default App
