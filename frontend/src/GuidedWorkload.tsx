import { SlidersHorizontal } from 'lucide-react'

type Route = {
  kind: string
  field: string
  weight: number
  weightLine: number
}

function parseRoutes(spec: string): Route[] {
  const lines = spec.split('\n')
  const routes: Route[] = []
  let withinQueries = false

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    if (/^queries:\s*(?:#.*)?$/.test(line)) {
      withinQueries = true
      continue
    }
    if (withinQueries && /^[A-Za-z_][A-Za-z0-9_-]*:\s*/.test(line)) break
    if (!withinQueries) continue

    const kind = line.match(/^  - kind:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$/)
    if (kind) {
      routes.push({ kind: kind[1], field: 'all records', weight: 0, weightLine: -1 })
      continue
    }
    const current = routes[routes.length - 1]
    if (!current) continue
    const field = line.match(/^    field:\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:#.*)?$/)
    if (field) current.field = field[1]
    const weight = line.match(/^    weight:\s*(0(?:\.\d+)?|1(?:\.0+)?)\s*(?:#.*)?$/)
    if (weight) {
      current.weight = Number(weight[1])
      current.weightLine = index
    }
  }
  return routes.filter((route) => route.weightLine >= 0)
}

function updateWeight(spec: string, routeIndex: number, newPercent: number): string {
  const routes = parseRoutes(spec)
  if (routes.length < 2 || routeIndex < 0 || routeIndex >= routes.length) return spec
  const max = 100 - (routes.length - 1)
  const selected = Math.min(max, Math.max(1, Math.round(newPercent)))
  const remaining = 100 - selected
  const others = routes.map((route, index) => ({ index, weight: route.weight })).filter((route) => route.index !== routeIndex)
  const available = remaining - others.length
  const originalSum = others.reduce((sum, route) => sum + route.weight, 0)
  const quotas = others.map((route) => {
    const share = originalSum > 0 ? route.weight / originalSum : 1 / others.length
    const exact = available * share
    return { index: route.index, allocation: Math.floor(exact), fractional: exact - Math.floor(exact) }
  })
  let outstanding = available - quotas.reduce((sum, quota) => sum + quota.allocation, 0)
  for (const quota of [...quotas].sort((a, b) => b.fractional - a.fractional || a.index - b.index)) {
    if (outstanding <= 0) break
    quota.allocation += 1
    outstanding -= 1
  }
  const percentages = new Array<number>(routes.length).fill(0)
  percentages[routeIndex] = selected
  for (const quota of quotas) percentages[quota.index] = quota.allocation + 1

  const lines = spec.split('\n')
  routes.forEach((route, index) => {
    lines[route.weightLine] = lines[route.weightLine].replace(
      /^(\s*weight:\s*)\S+/,
      (_, prefix: string) => `${prefix}${(percentages[index] / 100).toFixed(2)}`,
    )
  })
  return lines.join('\n')
}

const OP_NAMES: Record<string, string> = {
  point_lookup: 'Exact lookup',
  range_scan: 'Range search',
  filter: 'Filter records',
  insert: 'Add records',
  delete: 'Delete records',
  update: 'Update records',
}

export default function GuidedWorkload({ spec, onChange }: { spec: string; onChange: (value: string) => void }) {
  const routes = parseRoutes(spec)
  const recordCount = spec.match(/^record_count:\s*(\d+)/m)?.[1]
  const budget = spec.match(/^  memory_mb:\s*(\d+)/m)?.[1]
  const name = spec.match(/^name:\s*([^\n#]+)/m)?.[1]?.trim() ?? 'Current workload'
  const editable = routes.length >= 2 && routes.length <= 20
  const sum = routes.reduce((total, route) => total + route.weight, 0)

  return (
    <section className="guided-workload" aria-label="Visual workload editor">
      <div className="guided-heading">
        <span className="guided-icon"><SlidersHorizontal size={21} /></span>
        <div>
          <strong>Describe the workload</strong>
          <p>Set how often each operation happens.</p>
        </div>
      </div>
      <div className="guided-meta">
        <div><span>Workload</span><strong>{name.replaceAll('_', ' ')}</strong></div>
        <div><span>Records</span><strong>{recordCount ? Number(recordCount).toLocaleString() : '—'}</strong></div>
        <div><span>Memory budget</span><strong>{budget ? `${budget} MB` : 'Not specified'}</strong></div>
      </div>
      {editable ? (
        <div className="guided-routes">
          {routes.map((route, index) => (
            <label className="guided-route" key={`${route.kind}-${route.field}-${index}`}>
              <span className="guided-route-top">
                <span className="guided-route-name">{OP_NAMES[route.kind] ?? route.kind.replaceAll('_', ' ')} <small>· {route.field}</small></span>
                <strong>{Math.round(route.weight * 100)}%</strong>
              </span>
              <input
                type="range"
                min={1}
                max={100 - (routes.length - 1)}
                step={1}
                value={Math.min(100 - (routes.length - 1), Math.max(1, Math.round(route.weight * 100)))}
                onChange={(event) => onChange(updateWeight(spec, index, Number(event.target.value)))}
                aria-label={`Frequency of ${OP_NAMES[route.kind] ?? route.kind} on ${route.field}`}
              />
            </label>
          ))}
        </div>
      ) : <p className="guided-unavailable">This imported workload needs the advanced YAML editor. Visual controls work with standard MWS query routes that declare weights.</p>}
      <p className="guided-footnote">
        {editable
          ? `Operations total ${Math.round(sum * 100)}%. Adjusting one automatically balances the others. Predictions are not benchmark measurements.`
          : 'The original workload remains untouched. Use Advanced YAML below to edit it directly.'}
      </p>
    </section>
  )
}
