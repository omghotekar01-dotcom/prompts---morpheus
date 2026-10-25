import { useState } from 'react'
import { profileSubmittedCsv, type NativeCsvProfile, type SynthesisResult } from './api'
import './csv-data.css'

type Kind = 'point_lookup' | 'range_scan' | 'filter' | 'prefix_search'
type Route = { kind: Kind; field: string; weight: string; selectivity: string }

const KIND_LABELS: Record<Kind, string> = {
  point_lookup: 'Exact key lookup',
  range_scan: 'Ordered range search',
  filter: 'Filter matching values',
  prefix_search: 'String prefix search'
}

function newRoute(): Route {
  return { kind: 'point_lookup', field: '', weight: '1', selectivity: '' }
}

export default function CsvDataWorkspace({ onLoadWorkload }: {
  onLoadWorkload: (mws: string) => void
}) {
  const [csvText, setCsvText] = useState('')
  const [fileName, setFileName] = useState('')
  const [profile, setProfile] = useState<NativeCsvProfile | null>(null)
  const [inspectedText, setInspectedText] = useState('')
  const [routes, setRoutes] = useState<Route[]>([newRoute()])
  const [memoryLimit, setMemoryLimit] = useState('')
  const [result, setResult] = useState<SynthesisResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  function editCsv(next: string) {
    setCsvText(next)
    setProfile(null)
    setResult(null)
    setInspectedText('')
    setError('')
  }

  async function readFile(file: File | undefined) {
    if (!file) return
    if (file.size > 1_000_000) {
      setError('CSV exceeds 1 MB. Use a bounded dataset or partition before profiling.')
      return
    }
    try {
      editCsv(await file.text())
      setFileName(file.name)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  async function inspect() {
    setBusy(true)
    setError('')
    setResult(null)
    try {
      const response = await profileSubmittedCsv(csvText)
      setProfile(response.profile)
      setInspectedText(csvText)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(false)
    }
  }

  function updateRoute(index: number, update: Partial<Route>) {
    setRoutes((existing) => existing.map((item, i) =>
      i === index ? { ...item, ...update } : item
    ))
    setResult(null)
  }

  function validatedQueries() {
    if (!profile || inspectedText !== csvText) {
      throw new Error('Profile this exact CSV before selecting data structures.')
    }
    const known = new Set(profile.fields.map((field) => field.name))
    return routes.map((route, index) => {
      const weight = Number(route.weight)
      if (!known.has(route.field)) {
        throw new Error(`Query ${index + 1}: choose a real field from your CSV.`)
      }
      if (!Number.isFinite(weight) || weight <= 0) {
        throw new Error(`Query ${index + 1}: traffic weight must be positive.`)
      }
      const needsSelectivity = route.kind === 'range_scan' || route.kind === 'filter'
      const selectivity = Number(route.selectivity)
      if (needsSelectivity && (route.selectivity.trim() === '' ||
          !Number.isFinite(selectivity) || selectivity <= 0 || selectivity > 1)) {
        throw new Error(`Query ${index + 1}: enter selectivity between 0 and 1.`)
      }
      return {
        kind: route.kind,
        field: route.field,
        weight,
        ...(needsSelectivity ? { selectivity } : {})
      }
    })
  }

  function parsedMemory() {
    if (!memoryLimit.trim()) return undefined
    const value = Number(memoryLimit)
    if (!Number.isFinite(value) || value <= 0) {
      throw new Error('Memory limit must be a positive number of MB.')
    }
    return value
  }

  async function run() {
    setBusy(true)
    setError('')
    try {
      const queries = validatedQueries()
      const response = await profileSubmittedCsv(csvText, queries, parsedMemory())
      setProfile(response.profile)
      setResult(response.synthesis)
      setInspectedText(csvText)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    } finally {
      setBusy(false)
    }
  }

  function openWorkbench() {
    try {
      const queries = validatedQueries()
      const memory = parsedMemory()
      const fieldLines = profile!.fields.map((field) =>
        `  - name: ${field.name}\n    type: ${field.type}\n    cardinality: ${field.cardinality}`
      ).join('\n')
      const queryLines = queries.map((q) =>
        `  - kind: ${q.kind}\n    field: ${q.field}\n    weight: ${q.weight}` +
        (q.selectivity ? `\n    selectivity: ${q.selectivity}` : '')
      ).join('\n')
      onLoadWorkload(
        `version: mws-0.1\nname: submitted_csv_workload\nrecord_count: ${profile!.record_count}\n` +
        `fields:\n${fieldLines}\nqueries:\n${queryLines}\n` +
        (memory ? `constraints:\n  memory_mb: ${memory}\n` : '')
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause))
    }
  }

  return <main className="csv-page">
    <header className="csv-page-heading">
      <span className="section-kicker">REAL INPUT · C++20 DATA PROFILER</span>
      <h1>Optimize your own dataset</h1>
      <p>Load actual CSV records, inspect distinct values and data types with C++, then tell MORPHEUS how the records will be queried. No example dataset or predetermined answer is used.</p>
    </header>
    <section className="csv-surface">
      <div className="csv-step">
        <h2>1. Supply your data</h2>
        <p>CSV with a header row. Up to 1 MB, 100,000 records and 64 identifier-style column names.</p>
        <label className="csv-file-picker">Select CSV file
          <input type="file" accept=".csv,text/csv" onChange={(event) =>
            void readFile(event.currentTarget.files?.[0])
          }/>
        </label>
        {fileName && <span className="csv-file-name">{fileName}</span>}
        <label className="csv-field-label">Or paste CSV contents
          <textarea aria-label="CSV contents" spellCheck={false} value={csvText}
            onChange={(event) => editCsv(event.target.value)}
            placeholder="Paste your own CSV header and records here." rows={7}/>
        </label>
        <button className="primary-button" disabled={!csvText.trim() || busy}
          onClick={() => void inspect()}>{busy ? 'Processing…' : 'Analyze real CSV'}</button>
      </div>
      {profile && <div className="csv-step">
        <h2>2. Measured dataset characteristics</h2>
        <p><strong>{profile.record_count.toLocaleString()}</strong> actual records inspected by C++20. Cardinality is the exact number of distinct field values in the submitted CSV.</p>
        <div className="csv-table-scroll">
          <table><thead><tr><th>Field</th><th>Inferred type</th><th>Distinct values</th></tr></thead>
            <tbody>{profile.fields.map((field) => <tr key={field.name}>
              <td>{field.name}</td><td>{field.type}</td>
              <td>{field.cardinality.toLocaleString()}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <small>These are actual data-profile counts—not latency benchmarks or trained-model predictions.</small>
      </div>}
      {profile && <div className="csv-step">
        <h2>3. Describe real operations</h2>
        <p>Your data cannot reveal future query patterns automatically. Define the queries, relative frequency weights and constraints you care about.</p>
        {routes.map((route, index) => <div className="csv-route" key={index}>
          <label>Operation<select value={route.kind} onChange={(event) =>
            updateRoute(index, { kind: event.target.value as Kind, selectivity: '' })
          }>{Object.entries(KIND_LABELS).map(([value, title]) =>
            <option key={value} value={value}>{title}</option>)}</select></label>
          <label>Field<select value={route.field} onChange={(event) =>
            updateRoute(index, { field: event.target.value })
          }><option value="">Choose a field</option>{profile.fields.map((field) =>
            <option key={field.name} value={field.name}>{field.name}</option>)}</select></label>
          <label>Traffic weight<input value={route.weight} inputMode="decimal"
            onChange={(event) => updateRoute(index, { weight: event.target.value })}/></label>
          {(route.kind === 'range_scan' || route.kind === 'filter') &&
            <label>Selectivity (0–1)<input value={route.selectivity} inputMode="decimal"
              placeholder="e.g. 0.1" onChange={(event) =>
                updateRoute(index, { selectivity: event.target.value })}/></label>}
          {routes.length > 1 && <button className="csv-remove" onClick={() =>
            setRoutes((all) => all.filter((_, i) => i !== index))
          }>Remove query</button>}
        </div>)}
        <div className="csv-actions"><button className="secondary-button"
          disabled={routes.length >= 32}
          onClick={() => setRoutes((all) => [...all, newRoute()])}>Add query</button>
          <label>Optional memory limit (MB)<input value={memoryLimit} inputMode="decimal"
            placeholder="No limit" onChange={(event) => setMemoryLimit(event.target.value)}/></label></div>
        <div className="csv-actions">
          <button className="primary-button" disabled={busy} onClick={() => void run()}>
            {busy ? 'Searching…' : 'Run DSA optimization'}</button>
          <button className="secondary-button" onClick={openWorkbench}>Open editable MWS</button>
        </div>
      </div>}
      {error && <p className="csv-error" role="alert">{error}</p>}
      {result && <section className="csv-step csv-result">
        <h2>4. Search result</h2>
        {result.winner ? <>
          <strong>Best feasible evaluated configuration</strong>
          <p>{result.winner.unique_primitives.join(' + ')}</p>
          <p>Modeled latency: {result.winner.predicted_latency_us.toLocaleString()} μs · Modeled memory: {result.winner.predicted_memory_mb.toLocaleString()} MB</p>
        </> : <p>No evaluated configuration satisfies all requested constraints.</p>}
        <p><strong>Evidence:</strong> {result.evidence_state}. Modeled values must not be read as real measured benchmark performance.</p>
        {result.search_summary && <p>Search: {result.search_summary.strategy} · {result.search_summary.evaluated_configurations} evaluated configurations{result.search_summary.truncated ? ' · search budget truncated' : ''}</p>}
        {result.warnings.slice(0, 3).map((warning, i) => <p key={i} className="csv-warning">{warning}</p>)}
      </section>}
    </section>
  </main>
}
