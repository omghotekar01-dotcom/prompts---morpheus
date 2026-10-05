import { useEffect, useMemo, useState } from 'react'
import App from './App'
import {
  getApiSchemaContract,
  getCalibrationProfiles,
  getCapabilities,
  getDiagnostics,
  getEngineeringCompletion,
  getEvidence,
  getEvents,
  getFeatureRegistry,
  getRuns,
  getStateSummary,
  health,
  setSessionApiKey,
  verifyEvidenceLedger
} from './api'
import { getStartupMvpReadiness } from './startupMvp'

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
    id: 'startup-mvp',
    label: 'Startup MVP readiness',
    detail: 'Local product readiness, blockers and pilot deployment boundary',
    critical: true,
    run: async () => {
      const readiness = await getStartupMvpReadiness()
      if (!readiness.ready) {
        const blockers = readiness.blockers.length > 0 ? readiness.blockers.join(', ') : 'unknown'
        throw new Error(`Local startup MVP blockers: ${blockers}`)
      }
      return readiness
    }
  },
  {
    id: 'upgrade-contract',
    label: 'Upgrade contract',
    detail: 'Versioned feature policy and API route fingerprint',
    critical: true,
    run: async () => {
      const [features, contract] = await Promise.all([getFeatureRegistry(), getApiSchemaContract()])
      if (features.schema !== 'morpheus-feature-registry-v1') {
        throw new Error(`Unsupported feature registry: ${features.schema}`)
      }
      if (contract.schema !== 'morpheus-api-contract-fingerprint-v1' || contract.sha256.length !== 64) {
        throw new Error('API compatibility fingerprint is unavailable or malformed')
      }
      const blockedEnabled = features.features.some((feature) => feature.maturity === 'blocked' && feature.default_enabled)
      const unsafeResearchControl = features.features.some(
        (feature) => (feature.maturity === 'research' || feature.maturity === 'blocked') && feature.automatic_control_allowed
      )
      if (blockedEnabled || unsafeResearchControl) {
        throw new Error('Feature policy violates fail-closed maturity rules')
      }
      return { featureCount: features.features.length, apiContractSha256: contract.sha256 }
    }
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
    run: async () => {
      const [entries, verification] = await Promise.all([getEvidence(12), verifyEvidenceLedger()])
      if (!verification.valid) {
        throw new Error(`Evidence ledger integrity failed at sequence ${verification.failed_sequence ?? 'unknown'}`)
      }
      return { entries, verification }
    }
  }
]

function initialSteps(): StartupStepView[] {
  return STARTUP_STEPS.map((step) => ({ ...step, state: 'pending' }))
}

function startupError(step: StartupStep, error: unknown) {
  const message = error instanceof Error ? error.message : String(error)
  if (message === 'Not Found' || message.includes('404')) {
    return step.id === 'control-plane'
      ? 'MORPHEUS backend route not found. Restart with START-MORPHEUS.bat so a verified local backend port is selected.'
      : 'MORPHEUS backend endpoint is unavailable. Restart the launcher, then retry initialization.'
  }
  if (message.includes('Failed to fetch') || message.includes('NetworkError')) {
    return 'Cannot reach the MORPHEUS backend. Keep the backend terminal open or restart START-MORPHEUS.bat.'
  }
  return message
}

function StartupGate() {
  const [steps, setSteps] = useState<StartupStepView[]>(initialSteps)
  const [gateState, setGateState] = useState<GateState>('loading')
  const [attempt, setAttempt] = useState(0)
  const [limitedTelemetry, setLimitedTelemetry] = useState(false)
  const [apiKeyDraft, setApiKeyDraft] = useState('')

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
            const message = startupError(step, error)
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
  const failed = steps.filter((step) => step.state === 'failed')
  const ready = steps.filter((step) => step.state === 'ready').length
  const progress = Math.round((ready / steps.length) * 100)
  const currentStep = steps.find((step) => step.state === 'pending')
  const controlPlaneFailed = steps.find((step) => step.id === 'control-plane')?.state === 'failed'
  const apiKeyRequired = failed.some((step) => (step.error ?? '').includes('MORPHEUS API key required'))

  const unlockAndRetry = () => {
    const normalized = apiKeyDraft.trim()
    if (!normalized) return
    setSessionApiKey(normalized)
    setApiKeyDraft('')
    setAttempt((value) => value + 1)
  }

    const statusCopy = useMemo(() => {
    if (gateState === 'degraded' && controlPlaneFailed) {
      return 'MORPHEUS backend is unavailable. Restart the launcher, then retry initialization.'
    }
    if (gateState === 'degraded') return 'Required startup state is unavailable — retry or open the workspace in degraded mode.'
    if (gateState === 'ready' && limitedTelemetry) return 'Workspace is ready; some optional telemetry is unavailable.'
    if (gateState === 'ready') return 'Core services, compatibility contracts and workspace state are ready. Entering MORPHEUS.'
    return currentStep ? `Initializing ${currentStep.label.toLowerCase()}…` : 'Finalizing workspace…'
  }, [controlPlaneFailed, currentStep, gateState, limitedTelemetry])

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
              <div className="startup-kicker">WORKLOAD-AWARE DATA STRUCTURE ENGINE</div>
              <h1>MORPHEUS</h1>
              <p>{statusCopy}</p>
            </div>

            <div className="startup-progress" aria-label={`Startup readiness ${progress}%`}>
              <div className="startup-progress-track">
                <div className="startup-progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <div className="startup-progress-meta">
                <span>{progress}% ready</span>
                <span>{ready}/{steps.length} ready · {completed}/{steps.length} checked</span>
              </div>
            </div>

            <div className="startup-summary">
              <div>
                <strong>{gateState === 'degraded' ? 'Startup needs attention' : gateState === 'ready' ? 'Workspace ready' : 'Checking workspace'}</strong>
                <small>{failed.length > 0 ? `${failed.length} check${failed.length === 1 ? '' : 's'} need attention` : currentStep?.detail ?? 'All required checks completed.'}</small>
              </div>
              <span>{ready}/{steps.length}</span>
            </div>

            <details className="startup-details" open={gateState === 'degraded'}>
              <summary>{gateState === 'degraded' ? 'Review startup checks' : 'View technical startup checks'}</summary>
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
            </details>

            {gateState === 'degraded' && (
              <>
                {apiKeyRequired && <div className="startup-access">
                  <div><strong>Protected control plane</strong><small>This MORPHEUS instance requires its API key for protected routes. The key stays in browser session storage for this tab/session.</small></div>
                  <div className="startup-access-row"><input type="password" value={apiKeyDraft} onChange={(event) => setApiKeyDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') unlockAndRetry() }} placeholder="Enter X-Morpheus-Key" autoComplete="off" spellCheck={false}/><button className="startup-primary" onClick={unlockAndRetry} disabled={!apiKeyDraft.trim()}>Unlock & retry</button></div>
                </div>}
                <div className="startup-actions">
                  <button className="startup-primary" onClick={() => setAttempt((value) => value + 1)}>Retry initialization</button>
                  <button className="startup-secondary" onClick={() => setGateState('hidden')}>Open degraded workspace</button>
                  {failed.length > 0 && <span>{failed.length} startup check{failed.length === 1 ? '' : 's'} unavailable</span>}
                </div>
              </>
            )}

            <footer className="startup-footer">
              <span className="startup-pulse" aria-hidden="true" />
              <span>Checking real local services and evidence — no simulated readiness</span>
            </footer>
          </section>
        </div>
      )}
    </>
  )
}

export default StartupGate
