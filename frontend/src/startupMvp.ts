export interface StartupMvpReadinessCheck {
  id: string
  required: boolean
  passed: boolean
  detail: string
  evidence_state: string
  source: string
}

export interface StartupMvpReadiness {
  schema: 'morpheus-startup-mvp-readiness-v1'
  ready: boolean
  state: string
  startup_mvp_percent: number
  passed_checks: number
  total_checks: number
  checks: StartupMvpReadinessCheck[]
  blockers: string[]
  pilot_ready: boolean
  pilot_blockers: string[]
  pilot_configuration_blockers: string[]
  pilot_other_blockers: string[]
  advisories: string[]
  engineering_completion: {
    schema: string
    passed_gates: number
    total_gates: number
    percent: number
  }
  compatibility: {
    feature_registry_sha256: string
    api_contract_sha256: string
    api_route_count: number
  }
  environment: {
    python: string
    system: string
    machine: string
    toolchain: { kind: string; version: string } | null
  }
  scope: {
    readiness_target: string
    pilot_target: string
    hosted_multi_tenant_target: string
    production_deployment_authorized: boolean
    automatic_control_allowed: boolean
  }
  unsafe_feature_policy_findings: string[]
  missing_required_pilot_capabilities: string[]
  excluded_external_outcomes: string[]
  truth_boundaries: string[]
  readiness_sha256: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isSha256(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
}

export function validateStartupMvpReadiness(value: unknown): StartupMvpReadiness {
  if (!isRecord(value)) throw new Error('Startup MVP readiness response must be an object')
  if (value.schema !== 'morpheus-startup-mvp-readiness-v1') {
    throw new Error('Unsupported startup MVP readiness schema')
  }
  if (typeof value.ready !== 'boolean' || typeof value.pilot_ready !== 'boolean') {
    throw new Error('Startup MVP readiness flags are malformed')
  }
  if (typeof value.state !== 'string' || !value.state.startsWith('STARTUP_MVP_')) {
    throw new Error('Startup MVP readiness state is malformed')
  }
  if (
    typeof value.startup_mvp_percent !== 'number'
    || !Number.isFinite(value.startup_mvp_percent)
    || value.startup_mvp_percent < 0
    || value.startup_mvp_percent > 100
  ) {
    throw new Error('Startup MVP readiness percentage is malformed')
  }
  if (
    typeof value.passed_checks !== 'number'
    || typeof value.total_checks !== 'number'
    || value.passed_checks < 0
    || value.total_checks <= 0
    || value.passed_checks > value.total_checks
  ) {
    throw new Error('Startup MVP readiness check counts are malformed')
  }
  if (!Array.isArray(value.checks)) throw new Error('Startup MVP readiness checks are missing')
  for (const item of value.checks) {
    if (
      !isRecord(item)
      || typeof item.id !== 'string'
      || typeof item.required !== 'boolean'
      || typeof item.passed !== 'boolean'
      || typeof item.detail !== 'string'
      || typeof item.evidence_state !== 'string'
      || typeof item.source !== 'string'
    ) {
      throw new Error('Startup MVP readiness contains a malformed check')
    }
  }

  for (const [name, candidate] of [
    ['blockers', value.blockers],
    ['pilot_blockers', value.pilot_blockers],
    ['pilot_configuration_blockers', value.pilot_configuration_blockers],
    ['pilot_other_blockers', value.pilot_other_blockers],
    ['advisories', value.advisories],
    ['unsafe_feature_policy_findings', value.unsafe_feature_policy_findings],
    ['missing_required_pilot_capabilities', value.missing_required_pilot_capabilities],
    ['excluded_external_outcomes', value.excluded_external_outcomes],
    ['truth_boundaries', value.truth_boundaries]
  ] as const) {
    if (!isStringArray(candidate)) throw new Error(`Startup MVP readiness ${name} are malformed`)
  }

  if (!isRecord(value.engineering_completion)) throw new Error('Engineering completion summary is missing')
  if (
    typeof value.engineering_completion.schema !== 'string'
    || typeof value.engineering_completion.passed_gates !== 'number'
    || typeof value.engineering_completion.total_gates !== 'number'
    || typeof value.engineering_completion.percent !== 'number'
  ) {
    throw new Error('Engineering completion summary is malformed')
  }

  if (!isRecord(value.compatibility)) throw new Error('Compatibility summary is missing')
  if (
    !isSha256(value.compatibility.feature_registry_sha256)
    || !isSha256(value.compatibility.api_contract_sha256)
    || typeof value.compatibility.api_route_count !== 'number'
    || value.compatibility.api_route_count <= 0
  ) {
    throw new Error('Compatibility identities are malformed')
  }

  if (!isRecord(value.environment)) throw new Error('Environment summary is missing')
  if (
    typeof value.environment.python !== 'string'
    || typeof value.environment.system !== 'string'
    || typeof value.environment.machine !== 'string'
  ) {
    throw new Error('Environment summary is malformed')
  }
  if (value.environment.toolchain !== null) {
    if (
      !isRecord(value.environment.toolchain)
      || typeof value.environment.toolchain.kind !== 'string'
      || typeof value.environment.toolchain.version !== 'string'
    ) {
      throw new Error('Toolchain summary is malformed')
    }
  }

  if (!isRecord(value.scope)) throw new Error('Startup MVP scope is missing')
  if (
    value.scope.production_deployment_authorized !== false
    || value.scope.automatic_control_allowed !== false
    || typeof value.scope.readiness_target !== 'string'
    || typeof value.scope.pilot_target !== 'string'
    || typeof value.scope.hosted_multi_tenant_target !== 'string'
  ) {
    throw new Error('Startup MVP scope widens authority or is malformed')
  }

  if (!isSha256(value.readiness_sha256)) throw new Error('Startup MVP readiness digest is malformed')
  return value as unknown as StartupMvpReadiness
}

const STARTUP_MVP_TIMEOUT_MS = 10_000

export async function getStartupMvpReadiness(): Promise<StartupMvpReadiness> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), STARTUP_MVP_TIMEOUT_MS)
  try {
    const response = await fetch('/api/v2/system/startup-mvp-readiness', {
      method: 'GET',
      signal: controller.signal
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      const detail = isRecord(body) && typeof body.detail === 'string' ? body.detail : response.statusText
      throw new Error(detail || `Startup MVP readiness request failed with ${response.status}`)
    }
    return validateStartupMvpReadiness(await response.json())
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error(`Startup MVP readiness request timed out after ${STARTUP_MVP_TIMEOUT_MS / 1000}s`)
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}
