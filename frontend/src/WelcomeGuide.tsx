import { useState, type Dispatch, type FormEvent, type SetStateAction } from 'react'
import { ArrowRight, Bot, CheckCircle2, Code2, History, Play, Send, ShieldCheck, Sparkles, Workflow } from 'lucide-react'
import type { FullArtifactVerification, SynthesisResult } from './api'

export type GuideMessage = {
  id: number
  role: 'assistant' | 'user'
  text: string
}

export const INTRO_MESSAGE: GuideMessage = {
  id: 1,
  role: 'assistant',
  text: "Welcome to MORPHEUS. Tell me about a database or application, or select an example below. I can prepare a workload, run the actual design engine, show its C++ code, and check correctness.",
}

export type ExampleOption = { id: string; eyebrow: string; title: string; copy: string }

type Props = {
  messages: GuideMessage[]
  setMessages: Dispatch<SetStateAction<GuideMessage[]>>
  examples: readonly ExampleOption[]
  backendOnline: boolean
  aiConfigured: boolean
  hasResult: boolean
  runId?: string | null
  currentExample: string
  verificationSuccess: boolean | null
  onSelectExample: (id: string) => void
  onRun: () => Promise<SynthesisResult | null>
  onVerify: () => Promise<FullArtifactVerification | null>
  onExplain: (question: string) => Promise<string>
  onDraftCustom: (description: string) => Promise<void>
  onNavigate: (destination: string) => void
}

const topicToExample: Array<[RegExp, string]> = [
  [/student|college|university|admission|roll.number/i, 'students'],
  [/attendanc|classroom|lecture/i, 'attendance'],
  [/inventor|stock|warehouse/i, 'inventory'],
  [/hospital|clinic|appointment|patient/i, 'hospital'],
  [/bank|transaction|financ|payment/i, 'banking'],
  [/librar|book|isbn/i, 'library'],
  [/deliver|parcel|shipment|courier/i, 'delivery'],
  [/iot|sensor|factory|machine|industrial/i, 'iot'],
  [/support|helpdesk|complaint|ticket/i, 'support'],
  [/social|post|community|feed/i, 'social'],
  [/job|recruit|candidate|applicant/i, 'jobs'],
  [/restaurant|food|menu|outlet/i, 'restaurant'],
  [/session|token|auth|login/i, 'api-session'],
  [/catalog|product|ecommerce|e-commerce|online.shop/i, 'catalog'],
  [/event|analytic|log|telemetry/i, 'events'],
  [/experiment|local.measurement/i, 'measurement-pilot'],
]

export default function WelcomeGuide({
  messages,
  setMessages,
  examples,
  backendOnline,
  aiConfigured,
  hasResult,
  runId,
  currentExample,
  verificationSuccess,
  onSelectExample,
  onRun,
  onVerify,
  onExplain,
  onDraftCustom,
  onNavigate,
}: Props) {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [messageError, setMessageError] = useState<string | null>(null)

  const append = (role: GuideMessage['role'], text: string) => {
    setMessages((current) => [...current, { id: (current.at(-1)?.id ?? 0) + 1, role, text }])
  }

  const choose = (id: string) => {
    const example = examples.find((item) => item.id === id)
    if (!example) return
    onSelectExample(id)
    append('assistant', `Loaded "${example.title}" with a valid, editable workload specification. Open Workloads to change it, or select Run design to use the real backend.`)
  }

  const send = async (raw: string) => {
    const text = raw.trim()
    if (!text || busy) return
    append('user', text)
    setInput('')
    setMessageError(null)
    setBusy(true)
    try {
      const normalized = text.toLowerCase()
      const isInstruction = /\b(build|create|make|design|set up|prepare|sample|example|dataset|database|records)\b/i.test(normalized)
      const match = topicToExample.find(([pattern]) => pattern.test(text))
      if (/\b(why|explain|reason|how did|justify)\b/.test(normalized)) {
        if (!runId) {
          append('assistant', 'There is no saved synthesis run to explain yet. Select an example and run its design first, then I can answer from actual evidence.')
        } else {
          const answer = await onExplain(text)
          append('assistant', answer)
        }
      } else if (/\b(verify|verification|compile|correctness|test the code|check the code)\b/.test(normalized)) {
        if (!hasResult) {
          append('assistant', 'Verification requires generated code. Select an example and run the design first.')
        } else if (!backendOnline) {
          append('assistant', 'The backend is offline, so no real compiler or correctness check can run. Reconnect the engine before verifying.')
        } else {
          const report = await onVerify()
          append('assistant', report
            ? `Real verification finished. C++ compile: ${report.compile_gate.success ? 'PASSED' : 'FAILED'}. Behavioral checks: ${report.behavior_gate.success ? 'PASSED' : 'FAILED'} (${report.behavior_gate.checks} checks). Overall: ${report.success ? 'PASSED' : 'NEEDS ATTENTION'}. Open Synthesis Lab for the evidence.`
            : 'Verification did not complete. Check the error shown in the workspace, the local C++20 compiler, and backend connectivity.')
        }
      } else if (/\b(run|synthesi[sz]e|start design|find best|choose design|generate design)\b/.test(normalized)) {
        if (!backendOnline) {
          append('assistant', 'The engine is offline. Start MORPHEUS with the local launcher, then press Refresh connection. I cannot invent a synthesis result.')
        } else {
          const response = await onRun()
          append('assistant', response?.winner
            ? `The engine selected a real design using ${response.winner.unique_primitives.length} structure family/families for ${response.winner.assignments.length} operations. Model score: ${response.winner.score.toFixed(4)}. Open Synthesis Lab for the physical plan, or ask me to verify the code.`
            : 'Synthesis did not produce a selected design. Review the workspace error or adjust the constraints in Workloads.')
        }
      } else if (/\b(code|cpp|c\+\+|header|source)\b/.test(normalized)) {
        onNavigate('Code Generator')
        append('assistant', hasResult
          ? 'Opened Code Generator. It displays the C++20 returned by the real backend; choose Full Verification to test it.'
          : 'Opened Code Generator. The code area remains empty until you run a workload, so there is no fabricated preview.')
      } else if (/\b(history|previous run|old run|saved run)\b/.test(normalized)) {
        onNavigate('Experiment History')
        append('assistant', 'Opened the saved experiment history. You can resume a real run and compare decisions.')
      } else if (/\b(audit|evidence|ledger|security|hash)\b/.test(normalized)) {
        onNavigate('Audit & Evidence')
        append('assistant', 'Opened the evidence log. Its hash-chain status comes from the backend, not the chat.')
      } else if (/\b(status|diagnostic|compiler|machine|system)\b/.test(normalized)) {
        onNavigate('Machine Profiles')
        append('assistant', 'Opened the machine diagnostics. This shows which compiler and calibration information your local system actually reports.')
      } else if (/\b(workload|edit|yaml|customise|customize|configure)\b/.test(normalized) && !match) {
        onNavigate('Workloads')
        append('assistant', 'Opened Workloads. Adjust the sliders for common query mixes or expand Advanced YAML for the full specification.')
      } else if (match && (!aiConfigured || isInstruction)) {
        choose(match[1])
      } else if (aiConfigured) {
        await onDraftCustom(text)
        append('assistant', 'The connected language provider returned a draft and MORPHEUS validated it before applying it. Review its fields and query weights in Workloads, then run synthesis. If the draft does not match your intent, edit it before running.')
      } else {
        append('assistant', "I can load examples, run synthesis, show C++20, verify generated code, and explain saved evidence. For a new custom workload, choose a similar example and edit it in Workloads. Optional AI drafting requires a configured provider in Settings; this guided mode doesn't pretend to be a connected language model.")
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      setMessageError(reason)
      append('assistant', `That action could not finish: ${reason}. Your existing project and workload were not replaced by a fake result.`)
    } finally {
      setBusy(false)
    }
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void send(input)
  }
  const featured = showAll ? examples : examples.slice(0, 8)

  return (
    <div className="welcome-home">
      <div className="welcome-intro">
        <span className="welcome-kicker"><Sparkles size={16}/> YOUR DATA STRUCTURE WORKBENCH</span>
        <h2>What are you building?</h2>
        <p>Describe an application, pick a ready-made example, or continue a real result. MORPHEUS will guide you from workload to verified C++.</p>
        <div className="welcome-status">
          <span className={backendOnline ? 'online' : 'offline'}><span className="status-dot"/>{backendOnline ? 'Engine connected' : 'Engine offline'}</span>
          <span>{aiConfigured ? 'Custom AI drafting available' : 'Guided mode · AI optional'}</span>
          <span>{hasResult ? 'Design available' : 'No design run yet'}</span>
        </div>
      </div>
      <div className="welcome-layout">
        <section className="welcome-chat" aria-label="MORPHEUS interactive guide">
          <div className="welcome-chat-head">
            <span className="welcome-bot-icon"><Bot size={22}/></span>
            <div><strong>MORPHEUS Guide</strong><small>Step-by-step help, connected to real project actions</small></div>
          </div>
          <div className="welcome-messages" role="log" aria-label="Guide conversation" aria-live="polite" aria-relevant="additions">
            {messages.map((message) => <div className={`welcome-message ${message.role}`} key={message.id}>
              {message.role === 'assistant' && <span className="welcome-message-mark">M</span>}
              <p>{message.text}</p>
            </div>)}
            {busy && <div className="welcome-busy" role="status">Working on your request using the available project tools…</div>}
          </div>
          <div className="welcome-suggestions" aria-label="Suggested requests">
            {['Build a student database', 'Run design', 'Show generated C++', 'Verify the code'].map((suggestion) => (
              <button key={suggestion} disabled={busy} onClick={() => void send(suggestion)}>{suggestion}</button>
            ))}
          </div>
          <form onSubmit={submit} className="welcome-chat-form">
            <label htmlFor="morpheus-guide-input">Ask MORPHEUS</label>
            <div>
              <input id="morpheus-guide-input" value={input} onChange={(event) => setInput(event.target.value)} disabled={busy} placeholder="e.g. Build a library catalog or verify my C++" maxLength={2500}/>
              <button type="submit" disabled={!input.trim() || busy} aria-label="Send message"><Send size={19}/></button>
            </div>
          </form>
          <p className="welcome-chat-disclosure">Suggestions use built-in guided actions. Free-form AI drafting only runs when a language provider is configured; that text may be sent to the configured provider. MORPHEUS never fabricates performance or verification evidence.</p>
          {messageError && <p className="welcome-error" role="alert">{messageError}</p>}
        </section>
        <aside className="welcome-side">
          <section className="welcome-side-panel">
            <div className="welcome-section-title"><strong>Start with an example</strong><span>{examples.length} workloads</span></div>
            <p>All templates are synthetic and editable. Select one to prepare it.</p>
            <div className="welcome-examples">
              {featured.map((example) => (
                <button className={currentExample === example.id ? 'selected' : ''} key={example.id} disabled={busy} onClick={() => choose(example.id)}>
                  <span><strong>{example.title}</strong><small>{example.copy}</small></span>
                  <ArrowRight size={17}/>
                </button>
              ))}
            </div>
            {examples.length > 8 && <button className="welcome-show-all" onClick={() => setShowAll((current) => !current)}>{showAll ? 'Show fewer examples' : `View all ${examples.length} examples`}</button>}
          </section>
          <section className="welcome-side-panel welcome-next">
            <div className="welcome-section-title"><strong>Your next steps</strong></div>
            <button onClick={() => onNavigate('Workloads')}><span><Workflow size={18}/></span><div><strong>1. Review workload</strong><small>Change fields and operation mix</small></div><ArrowRight size={16}/></button>
            <button disabled={!backendOnline || busy} onClick={() => void send('Run design')}><span><Play size={18}/></span><div><strong>2. Run synthesis</strong><small>Choose a design using the real engine</small></div><ArrowRight size={16}/></button>
            <button onClick={() => onNavigate('Code Generator')}><span><Code2 size={18}/></span><div><strong>3. Inspect C++20</strong><small>{hasResult ? 'Generated code is ready' : 'Available after a successful run'}</small></div><ArrowRight size={16}/></button>
            <button disabled={!hasResult || busy} onClick={() => void send('Verify the code')}><span><ShieldCheck size={18}/></span><div><strong>4. Check correctness</strong><small>{verificationSuccess === true ? 'Compile and behavior passed' : verificationSuccess === false ? 'Review failing gates' : 'Requires a local C++ compiler'}</small></div><ArrowRight size={16}/></button>
            <button onClick={() => onNavigate('Experiment History')}><span><History size={18}/></span><div><strong>5. See saved runs</strong><small>Review decisions and evidence</small></div><ArrowRight size={16}/></button>
          </section>
          {hasResult && <button className="welcome-continue" onClick={() => onNavigate('Synthesis Lab')}><CheckCircle2 size={18}/> Continue current design <ArrowRight size={18}/></button>}
        </aside>
      </div>
    </div>
  )
}
