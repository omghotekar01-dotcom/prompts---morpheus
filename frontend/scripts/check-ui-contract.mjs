import { readFileSync } from 'node:fs'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api.ts', import.meta.url), 'utf8')
const themeToggle = readFileSync(new URL('../src/ThemeToggle.tsx', import.meta.url), 'utf8')
const productCss = readFileSync(new URL('../src/product.css', import.meta.url), 'utf8')
const themeCss = readFileSync(new URL('../src/theme.css', import.meta.url), 'utf8')
const startupGate = readFileSync(new URL('../src/StartupGate.tsx', import.meta.url), 'utf8')
const errorBoundary = readFileSync(new URL('../src/ErrorBoundary.tsx', import.meta.url), 'utf8')
const errorBoundaryCss = readFileSync(new URL('../src/error-boundary.css', import.meta.url), 'utf8')
const indexHtml = readFileSync(new URL('../index.html', import.meta.url), 'utf8')

const requiredPages = [
  'Workloads',
  'Synthesis Lab',
  'Decision Review',
  'Experiment History',
  'Engineering',
  'Cost Model',
  'Primitive Registry',
  'Search Space',
  'Code Generator',
  'Machine Profiles',
  'MORPHEUS Copilot',
  'Runtime Observatory',
  'Audit & Evidence'
]

const missingPages = requiredPages.filter((label) => !app.includes(`case '${label}'`))
if (missingPages.length) {
  throw new Error(`Functional page handlers are missing: ${missingPages.join(', ')}`)
}

const navStart = app.indexOf('const NAV_GROUPS')
const navEnd = app.indexOf('const PRIMITIVE_LABELS')
const navBlock = app.slice(navStart, navEnd)
for (const label of ['Command Center', 'Workloads', 'Synthesis Lab', 'Decision Review', 'Experiment History', 'Engineering', 'Audit & Evidence']) {
  if (!navBlock.includes(`label: '${label}'`)) throw new Error(`Primary navigation is missing ${label}`)
}
for (const advancedLabel of ['Cost Model', 'Primitive Registry', 'Search Space', 'Code Generator', 'Machine Profiles', 'MORPHEUS Copilot', 'Runtime Observatory']) {
  if (navBlock.includes(`label: '${advancedLabel}'`)) {
    throw new Error(`Advanced tool leaked back into primary navigation: ${advancedLabel}`)
  }
}

for (const fragment of ['ENGINEERING_DESTINATIONS', "label === 'Engineering' && ENGINEERING_DESTINATIONS.has(activeNav)", 'isNavItemActive(label)']) {
  if (!app.includes(fragment)) {
    throw new Error(`Advanced navigation context is missing: ${fragment}`)
  }
}

const requiredWiring = [
  'onClick={() => navigate(label)}',
  'onClick={() => setSettingsOpen(true)}',
  'onClick={() => void refreshControlPlane()}',
  'onClick={() => void run()}',
  'onClick={() => void verify()}',
  'onClick={() => void compareSearch()}',
  'onClick={() => void assessConfidence()}',
  'onClick={() => void resolveWithMeasurement()}',
  'onClick={() => void ask()}'
]

const missingWiring = requiredWiring.filter((fragment) => !app.includes(fragment))
if (missingWiring.length) {
  throw new Error(`Required UI action wiring is missing: ${missingWiring.join(' | ')}`)
}

if (!app.includes('Backend is offline') || !app.includes('Retry connection')) {
  throw new Error('The command center must expose an explicit backend-offline recovery state.')
}

if (!app.includes('Automatic production activation')) {
  throw new Error('The UI must preserve the automatic-production-control truth boundary.')
}

const requiredProductWorkflow = [
  'WORKLOAD_PRESETS',
  'Find the wrong data structure hiding in your hot path.',
  'Choose a starting workload',
  'downloadDecisionBrief',
  'Download decision brief',
  'Modeled estimates — not benchmark measurements'
]
const missingProductWorkflow = requiredProductWorkflow.filter((fragment) => !app.includes(fragment))
if (missingProductWorkflow.length) {
  throw new Error(`Startup decision workflow is incomplete: ${missingProductWorkflow.join(' | ')}`)
}

const requiredTraceDrafting = [
  'draftWorkloadFromAccessTrace',
  'Draft distribution semantics from an access trace',
  'Analyze & preview draft',
  'Apply draft to workload',
  'Research boundary',
  'eligible_for_runtime_automatic_control'
]
const missingTraceDrafting = requiredTraceDrafting.filter((fragment) => !app.includes(fragment) && !api.includes(fragment))
if (missingTraceDrafting.length) {
  throw new Error(`Trace-assisted workload drafting is incomplete: ${missingTraceDrafting.join(' | ')}`)
}
if (!api.includes('/api/v2/research/access-trace/apply-draft')) {
  throw new Error('Trace workload drafting API route is missing from the frontend contract.')
}

const requiredPersistenceWorkflow = [
  'getRunDetail',
  'resumePersistedRun',
  'Resume run',
  'Explain',
  'loadWorkloadFile',
  'downloadWorkloadSpec',
  'Import MWS',
  'Export MWS'
]
const missingPersistenceWorkflow = requiredPersistenceWorkflow.filter((fragment) => !app.includes(fragment) && !api.includes(fragment))
if (missingPersistenceWorkflow.length) {
  throw new Error(`Persisted workspace workflow is incomplete: ${missingPersistenceWorkflow.join(' | ')}`)
}
if (!api.includes('/api/runs/')) {
  throw new Error('Persisted run detail API wiring is missing.')
}

const requiredAIWorkflow = [
  'draftWorkloadWithAI',
  'getAIProviderStatus',
  'testAIProvider',
  'Generate validated MWS',
  'Apply to editor',
  'provider_assumptions',
  'authoritative_answer',
  'ai_rendered_answer',
  'View authoritative deterministic evidence answer',
  'Provider secrets are never entered in this browser UI.',
  'sent to that provider',
  "governed by that provider's data policy"
]
const missingAIWorkflow = requiredAIWorkflow.filter((fragment) => !app.includes(fragment) && !api.includes(fragment))
if (missingAIWorkflow.length) {
  throw new Error(`Optional AI workflow is incomplete: ${missingAIWorkflow.join(' | ')}`)
}
for (const route of ['/api/v2/ai/status', '/api/v2/ai/test', '/api/v2/ai/workload-draft']) {
  if (!api.includes(route)) throw new Error(`Optional AI API route is missing: ${route}`)
}

const requiredHotPathDoctor = [
  'diagnoseHotPath',
  'getHotPathDoctorOptions',
  'watchHotPath',
  'normalizeRealWorkloadTrace',
  'Hot Path Doctor',
  'Diagnose this hot path',
  'No fabricated speedup',
  'What is wrong with the current choice',
  'Workload-specific replacement',
  'MIGRATION PLAYBOOK',
  'Continue to Synthesis',
  'Diagnose my hot path',
  'PRODUCTION DRIFT WATCH',
  'Did traffic invalidate the old decision?',
  'Check recommendation validity',
  'Load TXT/CSV/JSON',
  'CSV / JSON key field (optional)',
  'normalized_window_sha256',
  'hotPathTraceImportGeneration',
  'invalidateHotPathTraceImport',
  'hotPathTraceImportBusy.baseline',
  'hotPathTraceImportBusy.observed',
  'Review observed workload in MORPHEUS',
  'DECISION FRESHNESS PASSPORT',
  'Export freshness passport',
  'Open human-controlled rollout & rollback ticket',
  'freshness_passport',
  'passport_sha256',
  'automatic_cutover_allowed',
  'eligible_for_runtime_automatic_control'
]
const missingHotPathDoctor = requiredHotPathDoctor.filter((fragment) => !app.includes(fragment) && !api.includes(fragment))
if (missingHotPathDoctor.length) {
  throw new Error(`Hot Path Doctor product workflow is incomplete: ${missingHotPathDoctor.join(' | ')}`)
}
for (const route of ['/api/v2/doctor/hot-path/options', '/api/v2/doctor/hot-path', '/api/v2/doctor/hot-path/watch', '/api/v2/doctor/hot-path/trace-intake']) {
  if (!api.includes(route)) throw new Error(`Hot Path Doctor API route is missing: ${route}`)
}

const requiredDecisionReview = [
  'Decision Review',
  'Assess decision confidence',
  'Run bounded local measurement',
  'Confidence intervals are deterministic engineering heuristics',
  'Machine-local evidence only',
  'measurement-pilot',
  'invalidateDecisionState',
  'editWorkload(event.target.value)',
  'changeSearchStrategy(event.target.value as SearchStrategy)'
]
const missingDecisionReview = requiredDecisionReview.filter((fragment) => !app.includes(fragment))
if (missingDecisionReview.length) {
  throw new Error(`Decision review workflow is incomplete: ${missingDecisionReview.join(' | ')}`)
}

const requiredGuidance = [
  'PRIMARY_WORKFLOW_DESTINATIONS',
  'workflowStages',
  'workflowCurrentStage',
  'nextAction',
  'workflow-guide',
  'next-action-card',
  "aria-current={isNavItemActive(label) ? 'page' : undefined}",
  "event.key === 'Escape'",
  "Backend unavailable",
  "Retry connection"
]
const missingGuidance = requiredGuidance.filter((fragment) => !app.includes(fragment) && !productCss.includes(fragment))
if (missingGuidance.length) {
  throw new Error(`Workflow guidance or recovery UX is incomplete: ${missingGuidance.join(' | ')}`)
}

if ((app.match(/title="Capability Matrix"/g) ?? []).length !== 1) {
  throw new Error('Capability Matrix must live only in the advanced Engineering workspace.')
}

for (const fragment of ['.workflow-guide {', '.workflow-progress {', '.next-action-card {']) {
  if (!productCss.includes(fragment)) throw new Error(`Workflow guidance styling is missing: ${fragment}`)
}


for (const fragment of ['Control-plane key', 'Use for this tab', 'Clear session key', 'apiAccessBlocked']) {
  if (!app.includes(fragment)) {
    throw new Error(`Session access settings are incomplete: ${fragment}`)
  }
}

const requiredContextSafety = [
  'selectedRunId',
  'explainPersistedRun',
  'const copilotRunId = selectedRunId ?? result?.run_id ?? null',
  'Choose a persisted run from Experiment History',
  'Workspace origin',
  'Current workspace /api route',
  'setSpecText(preset.spec)\n    invalidateDecisionState()',
  'Ask a question to load its evidence-grounded explanation.',
  'setCopilotAnswer(payload.run_id'
]
const missingContextSafety = requiredContextSafety.filter((fragment) => !app.includes(fragment))
if (missingContextSafety.length) {
  throw new Error(`Historical-run or dynamic-workspace context is incomplete: ${missingContextSafety.join(' | ')}`)
}

for (const forbidden of ['value="http://localhost:5173"', 'value="http://localhost:8000"']) {
  if (app.includes(forbidden)) throw new Error(`Dynamic launcher ports must not be hard-coded in settings: ${forbidden}`)
}

if (!startupGate.includes('startup-details') || !startupGate.includes('View technical startup checks')) {
  throw new Error('Startup technical checks must use progressive disclosure when the workspace is healthy.')
}

for (const fragment of ['Protected control plane', 'Unlock & retry', 'setSessionApiKey(normalized)', 'browser session storage']) {
  if (!startupGate.includes(fragment)) {
    throw new Error(`Guarded startup recovery is missing: ${fragment}`)
  }
}

for (const fragment of [
  '/api/v2/research/decision-confidence',
  '/api/v2/research/decision-resolve',
  'DecisionConfidenceResponse',
  'DecisionResolutionResponse'
]) {
  if (!api.includes(fragment)) {
    throw new Error(`Decision review API contract is missing: ${fragment}`)
  }
}

for (const fragment of [
  "const API_KEY_SESSION_KEY = 'morpheus-api-key'",
  'window.sessionStorage.getItem(API_KEY_SESSION_KEY)',
  "headers.set('X-Morpheus-Key', apiKey)",
  'setSessionApiKey',
  'hasSessionApiKey'
]) {
  if (!api.includes(fragment)) throw new Error(`Guarded browser authentication is missing: ${fragment}`)
}
if (api.includes('localStorage')) {
  throw new Error('Control-plane API credentials must not be persisted in localStorage.')
}

if (!startupGate.includes('WORKLOAD-AWARE DATA STRUCTURE ENGINE') || startupGate.includes('SELF-DESIGNING DATA STRUCTURE ENGINE')) {
  throw new Error('Startup positioning must be workload-first and avoid inflated self-design claims.')
}

if (!themeToggle.includes("return 'light'") || themeToggle.includes('prefers-color-scheme')) {
  throw new Error('MORPHEUS must open in light mode on first use while preserving an explicit stored theme choice.')
}

for (const fragment of ['--muted: #61708a;', '--muted-2: #62708a;']) {
  if (!themeCss.includes(fragment)) {
    throw new Error(`Light-theme readable text token is missing: ${fragment}`)
  }
}

for (const fragment of ['.topbar::before', '.startup-logo-orbit', '.agent-card { display: none; }', '.product-story {', '.preset-grid {', '.decision-review-summary {', '.decision-target-grid {', '.measured-candidate {', '.tool-grid {', '.copilot-context {', '.startup-summary {', '.session-access-card', '.startup-access {', '.trace-assistant {', '.trace-result {', '.history-run-row {', '.file-action {', '.ai-workload-assistant > summary', '.ai-settings-card {', '.copilot-authority {', '.hot-path-hero {', '.hot-path-start-grid {', '.doctor-playbook {', '.hot-path-watch > summary', '.hot-path-watch-result {', '.trace-key-field {', '.trace-intake-proof {', '.freshness-passport-card {', '.freshness-change-ticket {']) {
  if (!productCss.includes(fragment)) {
    throw new Error(`Calm product shell requirement is missing: ${fragment}`)
  }
}

if (!indexHtml.includes('name="theme-color" content="#f3f7ff"') || !indexHtml.includes('<title>MORPHEUS</title>')) {
  throw new Error('The document shell must match the light-first MORPHEUS product identity.')
}

for (const fragment of ['INTERFACE ERROR', 'The workspace view could not load.', 'This recovery screen does not']) {
  if (!errorBoundary.includes(fragment)) throw new Error(`Calm recovery copy is missing: ${fragment}`)
}
for (const forbidden of ['morpheus-fatal-ambient', 'radial-gradient', 'backdrop-filter']) {
  if (errorBoundary.includes(forbidden) || errorBoundaryCss.includes(forbidden)) {
    throw new Error(`Recovery screen must stay calm and non-showcase: ${forbidden}`)
  }
}

console.log(`MORPHEUS UI contract OK: ${requiredPages.length} functional pages, simplified primary navigation, ${requiredWiring.length} action bindings, context-safe history/Copilot flow, progressive startup disclosure, and calm light-first product shell checked.`)
