import { readFileSync } from 'node:fs'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')
const themeToggle = readFileSync(new URL('../src/ThemeToggle.tsx', import.meta.url), 'utf8')
const productCss = readFileSync(new URL('../src/product.css', import.meta.url), 'utf8')
const startupGate = readFileSync(new URL('../src/StartupGate.tsx', import.meta.url), 'utf8')
const indexHtml = readFileSync(new URL('../index.html', import.meta.url), 'utf8')

const requiredNavigation = [
  'Command Center',
  'Workloads',
  'Synthesis Lab',
  'Experiment History',
  'Cost Model',
  'Primitive Registry',
  'Search Space',
  'Code Generator',
  'Machine Profiles',
  'MORPHEUS Copilot',
  'Runtime Observatory',
  'Audit & Evidence'
]

const missingPages = requiredNavigation.filter((label) => !app.includes(`case '${label}'`) && label !== 'Command Center')
if (missingPages.length) {
  throw new Error(`Sidebar destinations without functional page handlers: ${missingPages.join(', ')}`)
}

const requiredWiring = [
  'onClick={() => navigate(label)}',
  'onClick={() => setSettingsOpen(true)}',
  'onClick={() => void refreshControlPlane()}',
  'onClick={() => void run()}',
  'onClick={() => void verify()}',
  'onClick={() => void compareSearch()}',
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

if (!startupGate.includes('WORKLOAD-AWARE DATA STRUCTURE ENGINE') || startupGate.includes('SELF-DESIGNING DATA STRUCTURE ENGINE')) {
  throw new Error('Startup positioning must be workload-first and avoid inflated self-design claims.')
}

if (!themeToggle.includes("return 'light'") || themeToggle.includes('prefers-color-scheme')) {
  throw new Error('MORPHEUS must open in light mode on first use while preserving an explicit stored theme choice.')
}

for (const fragment of ['.topbar::before', '.startup-logo-orbit', '.agent-card { display: none; }', '.product-story {', '.preset-grid {']) {
  if (!productCss.includes(fragment)) {
    throw new Error(`Calm product shell requirement is missing: ${fragment}`)
  }
}

if (!indexHtml.includes('name="theme-color" content="#f3f7ff"') || !indexHtml.includes('<title>MORPHEUS</title>')) {
  throw new Error('The document shell must match the light-first MORPHEUS product identity.')
}

console.log(`MORPHEUS UI contract OK: ${requiredNavigation.length} destinations, ${requiredWiring.length} action bindings, startup decision workflow, and calm light-first product shell checked.`)
