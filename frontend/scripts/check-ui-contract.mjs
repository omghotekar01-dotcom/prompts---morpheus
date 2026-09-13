import { readFileSync } from 'node:fs'

const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8')

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

console.log(`MORPHEUS UI contract OK: ${requiredNavigation.length} destinations and ${requiredWiring.length} action bindings checked.`)
