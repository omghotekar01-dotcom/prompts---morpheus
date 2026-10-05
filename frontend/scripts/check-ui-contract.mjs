import { readFileSync } from 'node:fs'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const api = readFileSync(new URL('../src/api.ts', import.meta.url), 'utf8')
const themeToggle = readFileSync(new URL('../src/ThemeToggle.tsx', import.meta.url), 'utf8')
const productCss = readFileSync(new URL('../src/product.css', import.meta.url), 'utf8')
const startupGate = readFileSync(new URL('../src/StartupGate.tsx', import.meta.url), 'utf8')
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
  'Stop choosing data structures by habit.',
  'Choose a starting workload',
  'downloadDecisionBrief',
  'Download decision brief',
  'Modeled estimates — not benchmark measurements'
]
const missingProductWorkflow = requiredProductWorkflow.filter((fragment) => !app.includes(fragment))
if (missingProductWorkflow.length) {
  throw new Error(`Startup decision workflow is incomplete: ${missingProductWorkflow.join(' | ')}`)
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

const requiredContextSafety = [
  'selectedRunId',
  'setSelectedRunId(item.run_id)',
  'const copilotRunId = selectedRunId ?? result?.run_id ?? null',
  'Choose a persisted run from Experiment History',
  'Workspace origin',
  'Current workspace /api route'
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

if (!startupGate.includes('WORKLOAD-AWARE DATA STRUCTURE ENGINE') || startupGate.includes('SELF-DESIGNING DATA STRUCTURE ENGINE')) {
  throw new Error('Startup positioning must be workload-first and avoid inflated self-design claims.')
}

if (!themeToggle.includes("return 'light'") || themeToggle.includes('prefers-color-scheme')) {
  throw new Error('MORPHEUS must open in light mode on first use while preserving an explicit stored theme choice.')
}

for (const fragment of ['.topbar::before', '.startup-logo-orbit', '.agent-card { display: none; }', '.product-story {', '.preset-grid {', '.decision-review-summary {', '.decision-target-grid {', '.measured-candidate {', '.tool-grid {', '.copilot-context {', '.startup-summary {']) {
  if (!productCss.includes(fragment)) {
    throw new Error(`Calm product shell requirement is missing: ${fragment}`)
  }
}

if (!indexHtml.includes('name="theme-color" content="#f3f7ff"') || !indexHtml.includes('<title>MORPHEUS</title>')) {
  throw new Error('The document shell must match the light-first MORPHEUS product identity.')
}

console.log(`MORPHEUS UI contract OK: ${requiredPages.length} functional pages, simplified primary navigation, ${requiredWiring.length} action bindings, context-safe history/Copilot flow, progressive startup disclosure, and calm light-first product shell checked.`)
