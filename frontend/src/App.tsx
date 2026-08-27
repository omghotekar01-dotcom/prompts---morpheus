import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  Blocks,
  Box,
  Braces,
  BrainCircuit,
  ChevronRight,
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
  CheckCircle2,
  AlertTriangle,
  type LucideIcon
} from 'lucide-react'
import { getEvents, health, synthesize, type CandidateResult, type EventItem, type SynthesisResult } from './api'
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
    title: 'MAIN',
    items: [
      { label: 'Command Center', icon: LayoutDashboard },
      { label: 'Workloads', icon: Braces },
      { label: 'Synthesis Lab', icon: Workflow },
      { label: 'Deployments', icon: Rocket },
      { label: 'Observatory', icon: Activity },
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
      { label: 'MORPHEUS Copilot', icon: BrainCircuit, badge: 'BETA' },
      { label: 'Research Notebook', icon: Network },
      { label: 'Audit & Evidence', icon: ShieldCheck }
    ]
  }
]

const PRIMITIVE_LABELS: Record<string, { label: string; glyph: string; className: string }> = {
  robin_hood_hash: { label: 'Robin Hood Hash', glyph: '#', className: 'cyan' },
  sorted_array: { label: 'Sorted Array', glyph: '≡', className: 'violet' },
  ordered_tree: { label: 'Ordered Tree', glyph: 'Y', className: 'blue' },
  radix_trie: { label: 'Radix Trie', glyph: 'Ψ', className: 'green' },
  bitmap: { label: 'Bitmap Filter', glyph: '▦', className: 'amber' },
  csr_graph: { label: 'CSR Graph', glyph: '⌘', className: 'pink' }
}

function formatNumber(value: number | undefined, digits = 2) {
  if (value === undefined || Number.isNaN(value)) return '—'
  return value.toLocaleString(undefined, { maximumFractionDigits: digits })
}

function App() {
  const [specText, setSpecText] = useState(SAMPLE_SPEC)
  const [result, setResult] = useState<SynthesisResult | null>(null)
  const [events, setEvents] = useState<EventItem[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backendOnline, setBackendOnline] = useState(false)
  const [activeNav, setActiveNav] = useState('Command Center')
  const [candidateView, setCandidateView] = useState<'feasible' | 'all'>('feasible')

  useEffect(() => {
    health()
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false))
    getEvents().then(setEvents).catch(() => undefined)
  }, [])

  const run = async () => {
    setRunning(true)
    setError(null)
    try {
      const payload = await synthesize(specText)
      setResult(payload)
      setBackendOnline(true)
      setEvents(await getEvents().catch(() => []))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  const winner = result?.winner ?? null
  const visibleCandidates = useMemo(() => {
    const list = result?.candidates ?? []
    return (candidateView === 'feasible' ? list.filter((candidate) => candidate.feasible) : list).slice(0, 8)
  }, [candidateView, result])

  return (
    <div className="app-shell">
      <aside className="sidebar glass-panel">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
          </div>
          <div>
            <strong>MORPHEUS</strong>
            <small>ENGINEERING SYSTEM</small>
          </div>
        </div>

        <div className="nav-scroll">
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-heading">{group.title}</div>
              {group.items.map(({ label, icon: Icon, badge }) => (
                <button
                  key={label}
                  className={`nav-item ${activeNav === label ? 'active' : ''}`}
                  onClick={() => setActiveNav(label)}
                >
                  <Icon size={17} strokeWidth={1.8} />
                  <span>{label}</span>
                  {badge && <em>{badge}</em>}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="agent-card">
          <div className="agent-title"><Sparkles size={15} /> MORPHEUS Agent <span>BETA</span></div>
          <p>Evidence-grounded assistant. Core synthesis stays deterministic without it.</p>
          <button className="secondary-button"><WandSparkles size={15} /> Open Copilot</button>
        </div>

        <button className="nav-item settings-item"><Settings size={17} /><span>Settings</span></button>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="headline">
            <div className="eyebrow">SELF-DESIGNING DATA STRUCTURE & ALGORITHM ENGINE</div>
            <h1>MORPHEUS <span>Command Center</span></h1>
            <p>Describe workload intent. MORPHEUS composes a feasible physical design, generates code, and builds an evidence trail.</p>
          </div>
          <div className="status-strip glass-panel">
            <div className="status-cell">
              <span className={`status-dot ${backendOnline ? 'online' : 'offline'}`} />
              <div><small>CONTROL PLANE</small><strong>{backendOnline ? 'ONLINE' : 'OFFLINE'}</strong></div>
            </div>
            <div className="status-cell">
              <ShieldCheck size={17} />
              <div><small>EVIDENCE MODE</small><strong>PREDICTED</strong></div>
            </div>
            <div className="status-cell">
              <KeyRound size={17} />
              <div><small>VERSION</small><strong>0.1.0</strong></div>
            </div>
          </div>
        </header>

        {error && (
          <div className="error-banner">
            <XCircle size={18} />
            <div><strong>Synthesis rejected</strong><span>{error}</span></div>
          </div>
        )}

        <section className="hero-grid">
          <article className="panel spec-panel">
            <PanelHeader number="01" title="WORKLOAD INPUT" subtitle="Declarative MWS specification" icon={Braces} />
            <div className="editor-toolbar">
              <div className="chip active">YAML</div>
              <div className="chip">MWS 0.1</div>
              <span className="toolbar-spacer" />
              <span className="tiny-status"><ShieldCheck size={13} /> safe parser</span>
            </div>
            <div className="editor-wrap">
              <div className="line-rail">{Array.from({ length: specText.split('\n').length }, (_, i) => <span key={i}>{i + 1}</span>)}</div>
              <textarea value={specText} onChange={(event) => setSpecText(event.target.value)} spellCheck={false} aria-label="MORPHEUS workload specification" />
            </div>
            <div className="panel-actions">
              <button className="primary-button" onClick={run} disabled={running}>
                {running ? <><TimerReset size={16} className="spin" /> Synthesizing…</> : <><Play size={16} fill="currentColor" /> Synthesize Design</>}
              </button>
              <span className="subtle-copy">Hard constraints are never relaxed silently.</span>
            </div>
          </article>

          <article className="panel engine-panel">
            <PanelHeader number="02" title="MORPHEUS ENGINE" subtitle="Validate → search → score → generate" icon={BrainCircuit} />
            <div className="pipeline">
              <PipelineStep icon={ShieldCheck} label="Validate" state={result ? 'done' : running ? 'active' : 'idle'} />
              <PipelineArrow />
              <PipelineStep icon={CircleGauge} label="Cost" state={running ? 'active' : result ? 'done' : 'idle'} />
              <PipelineArrow />
              <PipelineStep icon={Search} label="Search" state={running ? 'active' : result ? 'done' : 'idle'} />
              <PipelineArrow />
              <PipelineStep icon={Code2} label="Generate" state={result?.generated_code ? 'done' : 'idle'} />
            </div>
            <div className="search-surface">
              <div className="search-header"><span>SEARCH SUMMARY</span><strong>{result ? 'COMPLETE' : running ? 'RUNNING' : 'AWAITING RUN'}</strong></div>
              <div className="progress-track"><span style={{ width: result ? '100%' : running ? '64%' : '0%' }} /></div>
              <div className="metric-grid compact">
                <Metric label="Candidates" value={result ? String(result.candidates.length) : '—'} />
                <Metric label="Feasible" value={result ? String(result.candidates.filter((item) => item.feasible).length) : '—'} />
                <Metric label="Best score" value={winner ? formatNumber(winner.score, 4) : '—'} />
                <Metric label="Spec hash" value={result ? result.spec_hash.slice(0, 8) : '—'} mono />
              </div>
            </div>
            <div className="truth-callout">
              <Radar size={18} />
              <div><strong>Evidence boundary</strong><p>Current cost model uses deterministic bootstrap priors. These values are <b>predictions</b>, not target-machine measurements.</p></div>
            </div>
          </article>

          <article className="panel output-panel">
            <PanelHeader number="03" title="SELECTED DESIGN" subtitle="Lowest-score feasible candidate" icon={Box} />
            {winner ? (
              <>
                <div className="winner-orb"><Box size={34} /><span className="pulse-ring" /></div>
                <div className="winner-copy">
                  <span className="success-label"><CheckCircle2 size={14} /> FEASIBLE</span>
                  <h2>Candidate {winner.id}</h2>
                  <p>{winner.unique_primitives.length} physical primitives composed across {winner.assignments.length} operation routes.</p>
                </div>
                <div className="winner-list">
                  {winner.unique_primitives.map((primitive) => (
                    <div key={primitive}><CheckCircle2 size={14} /><span>{PRIMITIVE_LABELS[primitive]?.label ?? primitive}</span></div>
                  ))}
                </div>
                <button className="secondary-button wide"><Code2 size={15} /> Inspect Generated Code</button>
              </>
            ) : (
              <div className="empty-state">
                <Box size={34} />
                <strong>No selected configuration yet</strong>
                <p>Run synthesis to populate a real predicted design. MORPHEUS does not invent a result for the empty state.</p>
              </div>
            )}
          </article>
        </section>

        <section className="mid-grid">
          <article className="panel architecture-panel">
            <div className="section-head">
              <div><span className="section-kicker">PHYSICAL PLAN</span><h3>Recommended Composite Data Structure</h3></div>
              <div className="evidence-pill">{result?.evidence_state ?? 'NO EVIDENCE YET'}</div>
            </div>
            {winner ? <ArchitectureGraph winner={winner} /> : <ArchitectureSkeleton />}
          </article>

          <article className="panel metrics-panel">
            <div className="section-head">
              <div><span className="section-kicker">PREDICTED PERFORMANCE</span><h3>Cost Vector</h3></div>
              <span className="predicted-badge">MODEL OUTPUT</span>
            </div>
            <div className="metric-card-grid">
              <MetricCard icon={Gauge} label="Aggregate latency" value={winner ? `${formatNumber(winner.predicted_latency_us, 3)} μs` : '—'} caption="weighted proxy" />
              <MetricCard icon={MemoryStick} label="Memory" value={winner ? `${formatNumber(winner.predicted_memory_mb)} MB` : '—'} caption="unique structures" />
              <MetricCard icon={TimerReset} label="Build cost" value={winner ? `${formatNumber(winner.predicted_build_ms)} ms` : '—'} caption="bootstrap model" />
              <MetricCard icon={Activity} label="Update cost" value={winner ? `${formatNumber(winner.predicted_update_us, 3)} μs` : '—'} caption="mean primitive prior" />
            </div>
            <div className="resource-row">
              <Resource label="Correctness" value="Gate pending" icon={ShieldCheck} />
              <Resource label="Benchmark" value="P5 pending" icon={CircleGauge} />
              <Resource label="Deployment" value="Not deployed" icon={ServerCog} />
              <Resource label="Adaptation" value="Model only" icon={GitBranch} />
            </div>
          </article>
        </section>

        <section className="lower-grid">
          <article className="panel candidate-panel">
            <div className="section-head">
              <div><span className="section-kicker">SEARCH SPACE</span><h3>Candidate Explorer</h3></div>
              <div className="segmented">
                <button className={candidateView === 'feasible' ? 'active' : ''} onClick={() => setCandidateView('feasible')}>Feasible</button>
                <button className={candidateView === 'all' ? 'active' : ''} onClick={() => setCandidateView('all')}>All</button>
              </div>
            </div>
            <CandidateTable candidates={visibleCandidates} winnerId={winner?.id} />
          </article>

          <article className="panel runtime-panel">
            <div className="section-head">
              <div><span className="section-kicker">RUNTIME OBSERVATORY</span><h3>Adaptation Status</h3></div>
              <span className="status-chip muted">TELEMETRY OFFLINE</span>
            </div>
            <div className="runtime-empty">
              <Radar size={30} />
              <strong>No observed workload snapshot</strong>
              <p>Runtime counters and phase-change experiments arrive in P7. Until then, the dashboard refuses to display fabricated live telemetry.</p>
            </div>
            <div className="runtime-policy">
              <div><span>Switch policy</span><strong>benefit &gt; λ × cost + margin</strong></div>
              <div><span>Hysteresis</span><strong>specified / not yet live</strong></div>
              <div><span>Rollback</span><strong>future verification gate</strong></div>
            </div>
          </article>
        </section>

        <section className="bottom-grid">
          <article className="panel code-panel">
            <div className="section-head">
              <div><span className="section-kicker">GENERATED ARTIFACT</span><h3>C++20 Preview</h3></div>
              <div className="code-tabs"><span className="active">C++</span><span>Manifest</span><span>Tests</span></div>
            </div>
            <pre className="code-window"><code>{result?.generated_code ?? '// Run synthesis to generate a configuration-specific C++ preview.\n// P3 will add isolated compile + differential correctness before artifacts are marked verified.'}</code></pre>
          </article>

          <article className="panel deploy-panel">
            <div className="section-head">
              <div><span className="section-kicker">ARTIFACT PIPELINE</span><h3>Deployment Targets</h3></div>
            </div>
            <div className="deploy-options">
              <DeployOption icon={Blocks} label="Shared Library" detail="C++20 / .so / .dll" enabled={Boolean(result)} />
              <DeployOption icon={ServerCog} label="REST Service" detail="FastAPI wrapper" enabled={Boolean(result)} />
              <DeployOption icon={TerminalSquare} label="Embedded SDK" detail="future target" enabled={false} />
            </div>
            <button className="primary-button wide" disabled><Rocket size={15} /> Verify before deploy</button>
            <p className="guard-copy"><ShieldCheck size={13} /> Deployment remains locked until P3 compile/correctness gates exist.</p>
          </article>

          <article className="panel log-panel">
            <div className="section-head">
              <div><span className="section-kicker">CONTROL PLANE</span><h3>Activity Log</h3></div>
              <span className="status-chip">LIVE API</span>
            </div>
            <div className="event-list">
              {events.length ? events.slice(0, 7).map((event) => (
                <div className="event-row" key={`${event.timestamp}-${event.kind}`}>
                  <span className="event-time">{new Date(event.timestamp).toLocaleTimeString([], { hour12: false })}</span>
                  <span className={`event-mark ${event.kind.includes('failed') || event.kind.includes('rejected') ? 'bad' : ''}`} />
                  <div><strong>{event.kind.replaceAll('_', ' ')}</strong><p>{event.message}</p></div>
                </div>
              )) : (
                <div className="runtime-empty small"><Activity size={24} /><strong>No events yet</strong><p>Events appear here after validation or synthesis.</p></div>
              )}
            </div>
          </article>
        </section>

        <footer className="capability-bar glass-panel">
          <Capability icon={Braces} title="Declarative Intent" copy="MWS contract" />
          <Capability icon={Workflow} title="Automatic Synthesis" copy="typed search" />
          <Capability icon={Code2} title="Code Generation" copy="C++ preview" />
          <Capability icon={GitBranch} title="Runtime Adaptation" copy="policy scaffold" muted />
          <Capability icon={ShieldCheck} title="Deterministic & Safe" copy="hard gates" />
          <Capability icon={BrainCircuit} title="Agent-Ready" copy="optional AI" muted />
        </footer>
      </main>
    </div>
  )
}

function PanelHeader({ number, title, subtitle, icon: Icon }: { number: string; title: string; subtitle: string; icon: LucideIcon }) {
  return (
    <div className="panel-header">
      <div className="step-number">{number}</div>
      <Icon size={19} />
      <div><h3>{title}</h3><p>{subtitle}</p></div>
    </div>
  )
}

function PipelineStep({ icon: Icon, label, state }: { icon: LucideIcon; label: string; state: 'idle' | 'active' | 'done' }) {
  return (
    <div className={`pipeline-step ${state}`}>
      <div className="pipeline-icon">{state === 'done' ? <CheckCircle2 size={18} /> : <Icon size={18} />}</div>
      <span>{label}</span>
    </div>
  )
}

function PipelineArrow() { return <ChevronRight className="pipeline-arrow" size={16} /> }

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="metric"><span>{label}</span><strong className={mono ? 'mono' : ''}>{value}</strong></div>
}

function MetricCard({ icon: Icon, label, value, caption }: { icon: LucideIcon; label: string; value: string; caption: string }) {
  return (
    <div className="metric-card">
      <div className="metric-icon"><Icon size={17} /></div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{caption}</small>
      <svg viewBox="0 0 120 24" aria-hidden="true"><path d="M1 18 C14 19, 16 7, 29 10 S45 19, 55 11 S70 5, 80 12 S95 17, 119 6" /></svg>
    </div>
  )
}

function Resource({ label, value, icon: Icon }: { label: string; value: string; icon: LucideIcon }) {
  return <div className="resource"><Icon size={15} /><div><span>{label}</span><strong>{value}</strong></div></div>
}

function ArchitectureGraph({ winner }: { winner: CandidateResult }) {
  return (
    <div className="arch-flow">
      <div className="data-node"><Database size={22} /><strong>WORKLOAD</strong><small>{winner.assignments.length} routes</small></div>
      <div className="branch-lines" aria-hidden="true"><span/><span/><span/><span/></div>
      <div className="primitive-stack">
        {winner.assignments.map((assignment) => {
          const meta = PRIMITIVE_LABELS[assignment.primitive] ?? { label: assignment.primitive, glyph: '◆', className: 'cyan' }
          return (
            <div className={`primitive-row ${meta.className}`} key={`${assignment.query_index}-${assignment.primitive}`}>
              <div className="primitive-card"><b>{meta.glyph}</b><div><strong>{meta.label}</strong><span>{assignment.field ? `${assignment.field} index` : 'global structure'}</span></div></div>
              <div className="route-line"><span /></div>
              <div className="query-card"><strong>{assignment.query_kind.replaceAll('_', ' ')}</strong><small>{assignment.field ?? 'workload-wide'}</small></div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ArchitectureSkeleton() {
  return <div className="architecture-empty"><Workflow size={36} /><strong>Configuration graph is intentionally empty</strong><p>Submit a workload to render real operation → primitive routing.</p></div>
}

function CandidateTable({ candidates, winnerId }: { candidates: CandidateResult[]; winnerId?: string }) {
  if (!candidates.length) return <div className="table-empty"><Search size={24} /><span>No candidate evidence yet.</span></div>
  return (
    <div className="table-scroll">
      <table>
        <thead><tr><th>Candidate</th><th>Structures</th><th>Latency</th><th>Memory</th><th>Score</th><th>State</th></tr></thead>
        <tbody>
          {candidates.map((candidate) => (
            <tr key={candidate.id} className={candidate.id === winnerId ? 'winner-row' : ''}>
              <td className="mono">{candidate.id}{candidate.id === winnerId && <span className="winner-tag">WINNER</span>}</td>
              <td><div className="mini-chips">{candidate.unique_primitives.map((item) => <span key={item}>{PRIMITIVE_LABELS[item]?.label ?? item}</span>)}</div></td>
              <td>{formatNumber(candidate.predicted_latency_us, 3)} μs</td>
              <td>{formatNumber(candidate.predicted_memory_mb)} MB</td>
              <td>{formatNumber(candidate.score, 4)}</td>
              <td>{candidate.feasible ? <span className="ok-state"><CheckCircle2 size={13}/> Feasible</span> : <span className="bad-state"><AlertTriangle size={13}/> Rejected</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DeployOption({ icon: Icon, label, detail, enabled }: { icon: LucideIcon; label: string; detail: string; enabled: boolean }) {
  return <div className={`deploy-option ${enabled ? 'ready' : ''}`}><Icon size={21}/><div><strong>{label}</strong><span>{detail}</span></div>{enabled ? <CheckCircle2 size={15}/> : <span className="lock-dot"/>}</div>
}

function Capability({ icon: Icon, title, copy, muted = false }: { icon: LucideIcon; title: string; copy: string; muted?: boolean }) {
  return <div className={`capability ${muted ? 'muted' : ''}`}><Icon size={18}/><div><strong>{title}</strong><span>{copy}</span></div></div>
}

export default App
