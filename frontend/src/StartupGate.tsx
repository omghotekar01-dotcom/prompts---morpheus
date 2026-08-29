import { useEffect, useMemo, useState } from 'react'
import App from './App'
import {
  getCalibrationProfiles,
  getCapabilities,
  getDiagnostics,
  getEngineeringCompletion,
  getEvidence,
  getEvents,
  getRuns,
  getStateSummary,
  health,
  verifyEvidenceLedger
} from './api'

type StepState = 'pending' | 'ready' | 'failed'
type GateState = 'loading' | 'ready' | 'degraded' | 'hidden'

type StartupStep = {
  id: string
  label: string
  detail: string
  critical?: boolean
  run: () => Promise<unknown>
}

type StartupStepView = StartupStep & {
  state: StepState
  error?: string
}

const STARTUP_STEPS: StartupStep[] = [
  {
    id: 'control-plane',
    label: 'Control plane',
    detail: 'Backend health and service version',
    critical: true,
    run: () => health()
  },
  {
    id: 'engine',
    label: 'Engine integrity',
    detail: 'Capability graph and engineering completion gates',
    critical: true,
    run: async () => Promise.all([getCapabilities(), getEngineeringCompletion()])
  },
  {
    id: 'workspace',
    label: 'Workspace state',
    detail: 'Persisted metadata, recent synthesis runs and event history',
    critical: true,
    run: async () => Promise.all([getStateSummary(), getRuns(), getEvents()])
  },
  {
    id: 'machine',
    label: 'Machine profile',
    detail: 'Python, compiler and local toolchain diagnostics',
    run: () => getDiagnostics()
  },
  {
    id: 'calibration',
    label: 'Calibration registry',
    detail: 'Active machine-bound measurement profile',
    run: () => getCalibrationProfiles()
  },
  {
    id: 'evidence',
    label: 'Evidence ledger',
    detail: 'Recent evidence and tamper-evident chain verification',
    run: async () => Promise.all([getEvidence(12), verifyEvidenceLedger()])
  }
]

function initialSteps(): StartupStepView[] {
  return STARTUP_STEPS.map((step) => ({ ...step, state: 'pending' }))
}

function StartupGate() {
  const [steps, setSteps] = useState<StartupStepView[]>(initialSteps)
  const [gateState, setGateState] = useState<GateState>('loading')
  const [attempt, setAttempt] = useState(0)
  const [limitedTelemetry, setLimitedTelemetry] = useState(false)

  useEffect(() => {
    let active = true
    let hideTimer: number | undefined
    setSteps(initialSteps())
    setGateState('loading')
    setLimitedTelemetry(false)

    const execute = async () => {
      const outcomes = await Promise.all(
        STARTUP_STEPS.map(async (step) => {
          try {
            await step.run()
            if (active) {
              setSteps((current) => current.map((item) => (
                item.id === step.id ? { ...item, state: 'ready', error: undefined } : item
              )))
            }
            return { id: step.id, critical: Boolean(step.critical), ok: true }
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error)
            if (active) {
              setSteps((current) => current.map((item) => (
                item.id === step.id ? { ...item, state: 'failed', error: message } : item
              )))
            }
            return { id: step.id, critical: Boolean(step.critical), ok: false }
          }
        })
      )

      if (!active) return
      const criticalFailure = outcomes.some((outcome) => outcome.critical && !outcome.ok)
      if (criticalFailure) {
        setGateState('degraded')
        return
      }

      const optionalFailure = outcomes.some((outcome) => !outcome.critical && !outcome.ok)
      setLimitedTelemetry(optionalFailure)
      setGateState('ready')
      hideTimer = window.setTimeout(() => {
        if (active) setGateState('hidden')
      }, optionalFailure ? 900 : 420)
    }

    void execute()
    return () => {
      active = false
      if (hideTimer !== undefined) window.clearTimeout(hideTimer)
    }
  }, [attempt])

  const completed = steps.filter((step) => step.state !== 'pending').length
  const progress = Math.round((completed / steps.length) * 100)
  const currentStep = steps.find((step) => step.state === 'pending')
  const failed = steps.filter((step) => step.state === 'failed')
  const ready = steps.filter((step) => step.state === 'ready').length

  const statusCopy = useMemo(() => {
    if (gateState === 'degraded') return 'Required startup state is unavailable — retry or open the workspace in degraded mode.'
    if (gateState === 'ready' && limitedTelemetry) return 'Workspace is ready; some optional telemetry is unavailable.'
    if (gateState === 'ready') return 'Core services and workspace state are ready. Entering MORPHEUS.'
    return currentStep ? `Initializing ${currentStep.label.toLowerCase()}…` : 'Finalizing workspace…'
  }, [currentStep, gateState, limitedTelemetry])

  return (
    <>
      <App />
      {gateState !== 'hidden' && (
        <div className={`startup-screen ${gateState === 'ready' ? 'startup-screen--leaving' : ''}`}>
          <div className="startup-ambient startup-ambient--cyan" aria-hidden="true" />
          <div className="startup-ambient startup-ambient--violet" aria-hidden="true" />

          <section className="startup-card" aria-live="polite" aria-busy={gateState === 'loading'}>
            <div className="startup-logo-wrap" aria-hidden="true">
              <div className="startup-logo" />
              <div className="startup-logo-orbit" />
            </div>

            <div className="startup-heading">
              <div className="startup-kicker">SELF-DESIGNING DATA STRUCTURE ENGINE</div>
              <h1>MORPHEUS</h1>
              <p>{statusCopy}</p>
            </div>

            <div className="startup-progress" aria-label={`Initialization ${progress}% complete`}>
              <div className="startup-progress-track">
                <div className="startup-progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <div className="startup-progress-meta">
                <span>{progress}%</span>
                <span>{ready}/{steps.length} checks ready</span>
              </div>
            </div>

            <div className="startup-steps">
              {steps.map((step) => (
                <div className={`startup-step startup-step--${step.state}`} key={step.id}>
                  <span className="startup-step-dot" aria-hidden="true" />
                  <div>
                    <strong>{step.label}</strong>
                    <small>{step.state === 'failed' ? step.error ?? 'Unavailable' : step.detail}</small>
                  </div>
                </div>
              ))}
            </div>

            {gateState === 'degraded' && (
              <div className="startup-actions">
                <button className="startup-primary" onClick={() => setAttempt((value) => value + 1)}>Retry initialization</button>
                <button className="startup-secondary" onClick={() => setGateState('hidden')}>Open degraded workspace</button>
                {failed.length > 0 && <span>{failed.length} startup check{failed.length === 1 ? '' : 's'} unavailable</span>}
              </div>
            )}

            <footer className="startup-footer">
              <span className="startup-pulse" aria-hidden="true" />
              <span>Loading real project state — no simulated progress</span>
            </footer>
          </section>
        </div>
      )}
    </>
  )
}

export default StartupGate
