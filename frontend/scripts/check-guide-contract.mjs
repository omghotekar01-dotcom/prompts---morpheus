import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const app = read('../src/App.tsx')
const guide = read('../src/WelcomeGuide.tsx')
const examples = read('../src/workloadExamples.ts')
const styles = read('../src/welcome.css')
const entry = read('../src/main.tsx')

const required = [
  [app, "useState('Start')", 'chat-first entry'],
  [app, "case 'Start':", 'Start page route'],
  [app, '<WelcomeGuide', 'working guide mounted'],
  [app, 'runCompleteGuideDemo', 'complete demo action'],
  [app, 'verifyArtifactFull(specText)', 'real backend verification'],
  [app, 'draftWorkloadWithAI(description)', 'validated optional AI drafting'],
  [guide, 'onCompleteDemo()', 'complete demo wired to guide'],
  [guide, 'onRun()', 'synthesis from guide'],
  [guide, 'onVerify()', 'verification from guide'],
  [guide, 'onExplain(text)', 'evidence explanation from guide'],
  [guide, 'onDraftCustom(text)', 'custom AI workload from guide'],
  [guide, 'Engine offline', 'explicit degraded state'],
  [guide, 'configured provider', 'AI truth disclosure'],
  [guide, "role=\"log\"", 'accessible chat transcript'],
  [guide, 'Run complete demo', 'one-click demo button'],
  [entry, "import './welcome.css'", 'home styling included'],
  [styles, '.welcome-chat-form', 'chat composer styling'],
  [styles, '.welcome-full-demo', 'complete demo styling'],
]
for (const [text, snippet, purpose] of required) {
  if (!text.includes(snippet)) throw new Error(`Guide contract missing ${purpose}: ${snippet}`)
}

const found = [...examples.matchAll(/\{\s*id:\s*"([^"]+)"[\s\S]*?spec:\s*`([\s\S]*?)`/g)]
if (found.length !== 12) throw new Error(`Expected 12 additional synthetic examples; found ${found.length}`)
const ids = found.map((match) => match[1])
if (new Set(ids).size !== ids.length) throw new Error('Example IDs must be unique')

const validKinds = new Set(['point_lookup', 'range_scan', 'filter', 'prefix_search', 'graph_traversal', 'insert', 'update', 'delete'])
for (const [, id, spec] of found) {
  for (const header of ['version: mws-0.1', 'name:', 'record_count:', 'fields:', 'queries:', 'constraints:', 'objective:']) {
    if (!spec.includes(header)) throw new Error(`${id}: missing ${header}`)
  }
  const recordCount = Number(spec.match(/^record_count:\s*(\d+)$/m)?.[1])
  if (!Number.isSafeInteger(recordCount) || recordCount < 1) throw new Error(`${id}: invalid record count`)
  const fields = [...spec.matchAll(/^  - name:\s*(\w+)\n    type:\s*(\w+)\n    cardinality:\s*(\d+)/gm)]
  if (fields.length < 2) throw new Error(`${id}: no useful schema`)
  const fieldNames = new Set(fields.map((match) => match[1]))
  for (const [, field, type, cardinality] of fields) {
    if (!['uint32', 'uint64', 'string'].includes(type) || +cardinality < 1 || +cardinality > recordCount) {
      throw new Error(`${id}: invalid field ${field} type/cardinality`)
    }
  }
  const queries = [...spec.matchAll(/^  - kind:\s*(\w+)\n    field:\s*(\w+)\n    weight:\s*([01](?:\.\d+)?)\s*$/gm)]
  if (queries.length < 2) throw new Error(`${id}: needs multiple complete query routes`)
  const weightSum = queries.reduce((total, [, kind, field, weight]) => {
    if (!validKinds.has(kind)) throw new Error(`${id}: unsupported operation ${kind}`)
    if (!fieldNames.has(field)) throw new Error(`${id}: missing field ${field}`)
    if (!(Number(weight) > 0)) throw new Error(`${id}: non-positive route weight`)
    return total + Number(weight)
  }, 0)
  if (Math.abs(weightSum - 1) > 0.00001) throw new Error(`${id}: weights total ${weightSum} rather than 1`)
  const memory = Number(spec.match(/^  memory_mb:\s*(\d+)$/m)?.[1])
  if (!(memory >= 16)) throw new Error(`${id}: invalid memory budget`)
}
console.log(`MORPHEUS guided UX contract OK: chat-first flow, real engine actions, 12 synthetically valid examples and optional AI boundary checked.`)
