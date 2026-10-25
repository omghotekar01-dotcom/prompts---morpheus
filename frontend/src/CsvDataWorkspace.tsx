import { useEffect, useState } from 'react'
import {
  fetchDatasetCatalog, inspectDataset, pageDataset, probeDataset,
  type DatasetOptimizationInput, type DatasetPageResult, type DatasetProbeResult,
  type DatasetSource, type GeneratedDatasetArtifact, type NativeCsvProfile,
  type PrimitiveCatalogEntry, type QueryOptionReport, type SearchStrategy,
  type SynthesisResult
} from './api'
import './csv-data.css'

export interface SavedDataset {
  id: string
  name: string
  source: DatasetSource
}

type Kind = 'point_lookup' | 'range_scan' | 'filter' | 'prefix_search' | 'insert' | 'update' | 'delete'
type Route = {
  kind: Kind; field: string; weight: string; selectivity: string
  value: string; upperValue: string; observed: DatasetProbeResult | null
}
const KIND_LABELS: Record<Kind, string> = {
  point_lookup: 'Exact lookup', range_scan: 'Range search',
  filter: 'Equality filter (all matching rows)', prefix_search: 'String prefix',
  insert: 'Insert record (expected write workload)', update: 'Update record (expected write workload)',
  delete: 'Delete record (expected write workload)'
}
const PAGE_SIZE = 20
const FILE_LIMIT = 15_000_000
function blankRoute(): Route {
  return { kind: 'point_lookup', field: '', weight: '1', selectivity: '', value: '', upperValue: '', observed: null }
}
function fmt(number: number, digits = 3) {
  return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—'
}
function errorText(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}
function downloadText(name: string, source: string) {
  const url = URL.createObjectURL(new Blob([source], { type: 'text/plain;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}
async function readWorkbook(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Cannot read selected Excel workbook'))
    reader.onload = () => {
      const data = String(reader.result)
      const separator = data.indexOf(',')
      if (separator < 0) reject(new Error('Invalid workbook file data'))
      else resolve(data.slice(separator + 1))
    }
    reader.readAsDataURL(file)
  })
}
function isSelectivityKind(kind: Kind) {
  return kind === 'range_scan' || kind === 'filter'
}
function sourceSummary(source: DatasetSource) {
  return source.xlsx_base64 ? 'Excel .xlsx (active worksheet)' : 'CSV'
}

export default function CsvDataWorkspace({ onLoadWorkload, savedDatasets, onSaveDataset, onRemoveDataset }: {
  onLoadWorkload: (mws: string) => void
  savedDatasets: SavedDataset[]
  onSaveDataset: (entry: SavedDataset) => void
  onRemoveDataset: (id: string) => void
}) {
  const latest = savedDatasets[savedDatasets.length - 1]
  const [source, setSource] = useState<DatasetSource>(latest?.source ?? { csv_text: '' })
  const [fileName, setFileName] = useState(latest?.name ?? '')
  const [profile, setProfile] = useState<NativeCsvProfile | null>(null)
  const [page, setPage] = useState<DatasetPageResult | null>(null)
  const [pageError, setPageError] = useState('')
  const [routes, setRoutes] = useState<Route[]>([blankRoute()])
  const [memoryMb, setMemoryMb] = useState('')
  const [updateRate, setUpdateRate] = useState('0')
  const [objectives, setObjectives] = useState({ latency: '1', memory: '0.15', update: '0.2', build: '0.05' })
  const [strategy, setStrategy] = useState<SearchStrategy>('auto')
  const [candidateBudget, setCandidateBudget] = useState('256')
  const [catalog, setCatalog] = useState<PrimitiveCatalogEntry[]>([])
  const [options, setOptions] = useState<QueryOptionReport[]>([])
  const [result, setResult] = useState<SynthesisResult | null>(null)
  const [artifact, setArtifact] = useState<GeneratedDatasetArtifact | null>(null)
  const [codeError, setCodeError] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [busy, setBusy] = useState(false)
  const [pageBusy, setPageBusy] = useState(false)
  const [probeBusy, setProbeBusy] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    void fetchDatasetCatalog().then((data) => setCatalog(data.primitives)).catch(() => {
      // The dataset API itself will provide an explicit error when requested.
    })
  }, [])

  function resetData(next: DatasetSource, label: string) {
    setSource(next)
    setFileName(label)
    setProfile(null)
    setPage(null)
    setPageError('')
    setRoutes([blankRoute()])
    setResult(null)
    setArtifact(null)
    setOptions([])
    setError('')
  }

  async function readFile(file: File | undefined) {
    if (!file) return
    if (file.size > FILE_LIMIT) {
      setError('The selected file exceeds the 15 MB import limit. Use a smaller file or partition it.')
      return
    }
    try {
      if (file.name.toLowerCase().endsWith('.xlsx')) {
        const content = { xlsx_base64: await readWorkbook(file) }
        resetData(content, file.name)
        onSaveDataset({ id: crypto.randomUUID(), name: file.name, source: content })
      } else if (file.name.toLowerCase().endsWith('.csv')) {
        const content = { csv_text: await file.text() }
        resetData(content, file.name)
        onSaveDataset({ id: crypto.randomUUID(), name: file.name, source: content })
      } else {
        setError('Choose a .csv or .xlsx file. Legacy .xls is not supported.')
      }
    } catch (cause) {
      setError(errorText(cause))
    }
  }

  async function loadPage(offset: number) {
    if (!profile) return
    setPageBusy(true)
    setPageError('')
    try {
      const response = await pageDataset(source, offset, PAGE_SIZE)
      if (response.source_sha256 !== profile.source_sha256) throw new Error('Dataset changed; profile it again.')
      setPage(response)
    } catch (cause) {
      setPageError(errorText(cause))
    } finally {
      setPageBusy(false)
    }
  }

  async function inspect() {
    setBusy(true)
    setError('')
    setPageError('')
    setResult(null)
    setArtifact(null)
    setOptions([])
    setPage(null)
    try {
      const inspected = await inspectDataset(source)
      setProfile(inspected.profile)
      setRoutes([blankRoute()])
      // Page reading is independent; a missing newer native CLI must not hide profile information.
      try {
        const first = await pageDataset(source, 0, PAGE_SIZE)
        if (first.source_sha256 === inspected.profile.source_sha256) setPage(first)
      } catch (cause) {
        setPageError(errorText(cause))
      }
    } catch (cause) {
      setProfile(null)
      setError(errorText(cause))
    } finally {
      setBusy(false)
    }
  }

  function updateRoute(index: number, changes: Partial<Route>) {
    setRoutes((old) => old.map((route, i) => i === index ? {
      ...route, ...changes, observed: null
    } : route))
    setResult(null)
    setOptions([])
    setArtifact(null)
  }

  function invalidateDecision() {
    setResult(null)
    setArtifact(null)
    setOptions([])
    setCodeError('')
  }

  function checkNumber(raw: string, label: string, positive: boolean): number {
    if (raw.trim() === '') throw new Error(label + ' is required')
    const number = Number(raw)
    if (!Number.isFinite(number) || (positive ? number <= 0 : number < 0)) {
      throw new Error(label + (positive ? ' must be positive' : ' cannot be negative'))
    }
    return number
  }

  function buildInput(): DatasetOptimizationInput {
    if (!profile) throw new Error('Analyze your real dataset before optimization.')
    const fields = new Map(profile.fields.map((field) => [field.name, field]))
    const queries = routes.map((route, index) => {
      const field = fields.get(route.field)
      if (!field) throw new Error('Operation ' + (index + 1) + ': choose a column from the uploaded file.')
      if (route.kind === 'prefix_search' && field.type !== 'string') {
        throw new Error('Prefix search requires a string column.')
      }
      const weight = checkNumber(route.weight, 'Operation weight', true)
      let selectivity: number | undefined
      if (isSelectivityKind(route.kind)) {
        selectivity = checkNumber(route.selectivity, 'Filter/range selectivity', true)
        if (selectivity > 1) throw new Error('Filter/range selectivity cannot exceed 1.')
      }
      return { kind: route.kind, field: route.field, weight, ...(selectivity === undefined ? {} : { selectivity }) }
    })
    const memory = memoryMb.trim() ? checkNumber(memoryMb, 'Memory budget (MB)', true) : undefined
    const update = checkNumber(updateRate, 'Update rate', false)
    const weights = {
      latency: checkNumber(objectives.latency, 'Latency objective', false),
      memory: checkNumber(objectives.memory, 'Memory objective', false),
      update: checkNumber(objectives.update, 'Update objective', false),
      build: checkNumber(objectives.build, 'Build objective', false)
    }
    if (Object.values(weights).every((value) => value === 0)) throw new Error('Enable at least one objective.')
    const max = checkNumber(candidateBudget, 'Candidate budget', true)
    if (!Number.isInteger(max) || max > 10_000) throw new Error('Candidate budget must be an integer from 1 to 10,000.')
    return {
      ...source, queries, constraints: { ...(memory === undefined ? {} : { memory_mb: memory }), update_rate: update },
      objective: weights, strategy, max_candidates: max
    }
  }

  async function runOptimization() {
    setBusy(true)
    setError('')
    setResult(null)
    setArtifact(null)
    try {
      const response = await inspectDataset(buildInput())
      if (response.profile.source_sha256 !== profile?.source_sha256) throw new Error('Source file changed during optimization.')
      setResult(response.synthesis)
      setOptions(response.options_by_query ?? [])
      setArtifact(response.generated_artifact ?? null)
      setCodeError(response.generated_artifact_error ?? '')
      setShowAll(false)
    } catch (cause) {
      setError(errorText(cause))
    } finally {
      setBusy(false)
    }
  }

  async function probeRoute(index: number) {
    const route = routes[index]
    if (!route.field) { setError('Choose a column before querying records.'); return }
    if (route.kind === 'range_scan' && !route.upperValue.trim()) {
      setError('Enter the range upper value for a real-data scan.'); return
    }
    setError('')
    setProbeBusy(index)
    try {
      const report = await probeDataset(source, route.field, route.kind, route.value,
        route.kind === 'range_scan' ? route.upperValue : undefined)
      if (report.source_sha256 !== profile?.source_sha256) throw new Error('Source data changed; re-analyze it.')
      setRoutes((existing) => existing.map((item, i) => i !== index ? item : ({
        ...item, observed: report,
        ...(isSelectivityKind(item.kind) ? { selectivity: String(report.matched_selectivity) } : {})
      })))
      setResult(null)
      setArtifact(null)
      setOptions([])
    } catch (cause) {
      setError(errorText(cause))
    } finally {
      setProbeBusy(null)
    }
  }

  function openWorkbench() {
    try {
      const input = buildInput()
      const queryLines = (input.queries ?? []).map((q) => [
        '  - kind: ' + q.kind, '    field: ' + q.field, '    weight: ' + q.weight,
        ...(q.selectivity === undefined ? [] : ['    selectivity: ' + q.selectivity])
      ].join('\n')).join('\n')
      const fieldLines = profile!.fields.map((field) => (
        '  - name: ' + field.name + '\n    type: ' + field.type + '\n    cardinality: ' + field.cardinality
      )).join('\n')
      const mem = input.constraints?.memory_mb
      const obj = input.objective!
      onLoadWorkload([
        'version: mws-0.1', 'name: uploaded_' + (profile!.source_kind ?? 'csv').toLowerCase(),
        'record_count: ' + profile!.record_count, 'fields:', fieldLines,
        'queries:', queryLines, 'constraints:',
        ...(mem === undefined ? [] : ['  memory_mb: ' + mem]),
        '  update_rate: ' + (input.constraints?.update_rate ?? 0),
        'objective:', '  latency: ' + obj.latency, '  memory: ' + obj.memory,
        '  update: ' + obj.update, '  build: ' + obj.build
      ].join('\n'))
    } catch (cause) {
      setError(errorText(cause))
    }
  }

  const hasSource = Boolean(source.csv_text?.trim() || source.xlsx_base64)
  const shown = showAll ? result?.candidates : result?.candidates.slice(0, 25)
  // Derive suggestions from the actual rows returned by the native C++ CSV reader.
  // No domain-specific values or student-only column names are injected.
  function observedValues(fieldName: string): string[] {
    if (!page || !profile) return []
    const position = profile.fields.findIndex((field) => field.name === fieldName)
    if (position < 0) return []
    return [...new Set(page.records.map((record) => record.values[position] ?? ''))]
      .filter((value) => value.trim() !== '').slice(0, 20)
  }

  const offeredKinds = (Object.keys(KIND_LABELS) as Kind[]).filter((kind) =>
    !catalog.length || catalog.some((entry) => entry.operations.includes(kind)))
  const feasibleCandidates = result?.candidates.filter((candidate) => candidate.feasible) ?? []
  const distinctAlternatives = [...new Set(feasibleCandidates.flatMap((candidate) =>
    candidate.assignments.map((assignment) => assignment.primitive)))]
    .map((primitive) => {
      const candidates = feasibleCandidates.filter((candidate) =>
        candidate.assignments.some((assignment) => assignment.primitive === primitive))
      const best = candidates.reduce((current, candidate) =>
        !current || candidate.score < current.score ? candidate : current, undefined as typeof candidates[number] | undefined)
      return { primitive, best, count: candidates.length }
    }).sort((a, b) => (a.best?.score ?? Infinity) - (b.best?.score ?? Infinity))

  return <main className="csv-page">
    <header className="csv-page-heading">
      <span className="section-kicker">REAL DATA · C++20 DSA SEARCH · AUDITABLE CANDIDATES</span>
      <h1>Dataset → workload → physical plan</h1>
      <p>Upload any supported CSV or Excel schema. Dataset records and column names come from your file; the query mix, constraints and objectives come from you. MORPHEUS evaluates the actual registered index implementations—no student-specific field list or preset winner.</p>
    </header>
    <section className="csv-surface">
      <section className="csv-step">
        <h2>1 · Import real records</h2>
        <p>Select a CSV or .xlsx workbook (first active worksheet). Maximum 15 MB, 100,000 records, 64 columns. Original column names are preserved and mapped to safe C++ identifiers.</p>
        <label className="csv-file-picker">Choose your own dataset
          <input type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(event) => { void readFile(event.currentTarget.files?.[0]); event.currentTarget.value = '' }}/>
        </label>
        {fileName && <span className="csv-file-name">{fileName} · {sourceSummary(source)}</span>}
        <div className="csv-library">
          <h3>Datasets added in this browser session ({savedDatasets.length})</h3>
          <p>Switch between uploaded files without renaming columns to a predefined schema. Browser refresh clears this in-memory list; local files are not persisted on the server.</p>
          {savedDatasets.map((item) => <div className="csv-library-item" key={item.id}>
            <button className="secondary-button" onClick={() => resetData(item.source, item.name)}>
              Open {item.name} ({item.source.xlsx_base64 ? 'XLSX' : 'CSV'})
            </button>
            <button className="csv-remove" onClick={() => onRemoveDataset(item.id)}>Forget from session</button>
          </div>)}
          {!source.xlsx_base64 && Boolean(source.csv_text?.trim()) && <button className="secondary-button"
            onClick={() => onSaveDataset({ id: crypto.randomUUID(), name: fileName || 'Pasted dataset', source })}>
            Keep current pasted CSV in session list
          </button>}
        </div>
        {!source.xlsx_base64 && <label className="csv-field-label">Or paste CSV with any column headings
          <textarea spellCheck={false} aria-label="CSV contents" value={source.csv_text ?? ''}
            onChange={(event) => resetData({ csv_text: event.target.value }, '')}
            placeholder={'Product Name,Price (INR),Stock\nMouse,499,12\nKeyboard,799,8'} rows={5}/>
        </label>}
        <button className="primary-button" disabled={!hasSource || busy} onClick={() => void inspect()}>
          {busy ? 'Inspecting…' : 'Analyze uploaded dataset using C++'}
        </button>
      </section>
      {profile && <section className="csv-step">
        <h2>2 · Actual dataset profile</h2>
        <p><strong>{fmt(profile.record_count, 0)}</strong> records · <strong>{profile.fields.length}</strong> columns · {profile.source_kind ?? 'CSV'}{profile.worksheet ? ' · sheet: ' + profile.worksheet : ''}</p>
        <p>Measured cardinality means exactly how many distinct values occurred in each uploaded column. This is not a benchmark of Robin Hood Hash, Bitmap, or another index.</p>
        <div className="csv-table-scroll"><table><thead><tr><th>Original uploaded column</th><th>Safe C++ identifier</th><th>Detected type</th><th>Actual distinct values</th></tr></thead>
          <tbody>{profile.fields.map((field) => <tr key={field.name}>
            <td>{field.source_name ?? field.name}</td><td><code>{field.name}</code></td>
            <td>{field.type}</td><td>{fmt(field.cardinality, 0)}</td>
          </tr>)}</tbody></table></div>
        <small>Input SHA-256: {profile.source_sha256} · {profile.provenance}</small>
        <h3>Browse the actual uploaded records</h3>
        {page && <><p>Showing rows {page.records.length ? page.offset + 1 : 0}–{page.offset + page.records.length} of {fmt(page.total_records, 0)}. Every page is parsed by the compiled C++ CSV reader.</p>
          <div className="csv-table-scroll"><table><thead><tr><th>#</th>{page.source_columns.map((name, i) => <th key={i}>{name || 'Column ' + (i + 1)}</th>)}</tr></thead>
            <tbody>{page.records.map((record) => <tr key={record.record_index}>
              <td>{record.record_index}</td>{record.values.map((cell, i) => <td key={i}>{cell}</td>)}
            </tr>)}</tbody></table></div>
          <div className="csv-actions"><button className="secondary-button" disabled={pageBusy || page.offset === 0}
              onClick={() => void loadPage(Math.max(0, page.offset - PAGE_SIZE))}>Previous 20</button>
            <button className="secondary-button" disabled={pageBusy || page.offset + PAGE_SIZE >= page.total_records}
              onClick={() => void loadPage(page.offset + PAGE_SIZE)}>Next 20</button></div>
        </>}
        {pageError && <p className="csv-warning">Row browsing: {pageError}. The dataset profile remains available.</p>}
      </section>}
      <section className="csv-step">
        <h2>3 · All implemented DSA options</h2>
        <p>This is the versioned implementation registry, not a list of hardcoded answers. Every option has a capability and physical source implementation; only eligible options enter each query's search space.</p>
        {catalog.length ? <div className="csv-table-scroll"><table><thead><tr><th>Real index implementation</th><th>Supported operations</th><th>Implementation source</th></tr></thead>
          <tbody>{catalog.map((p) => <tr key={p.id}><td><strong>{p.name}</strong><br/><small>{p.implementation_id}</small></td>
            <td>{p.operations.join(', ')}</td><td><code>{p.source_path ?? 'No source path'}</code></td></tr>)}</tbody>
        </table></div> : <p>Catalog not available yet. Start the MORPHEUS backend to load the actual registry.</p>}
        <small>Registry cost constants are labeled bootstrap priors. They are not measured performance of your uploaded dataset.</small>
      </section>
      {profile && <section className="csv-step">
        <h2>4 · Define the actual workload</h2>
        <p>Choose any uploaded column. The operation menu is derived from actual registered index capabilities, including read and write workloads. Enter expected operation frequency, real predicates, memory budget and objectives. Imported records are never silently modified.</p>
        {routes.map((route, index) => <div className="csv-route" key={index}>
          <label>Operation<select value={route.kind} onChange={(e) => updateRoute(index, { kind: e.target.value as Kind, selectivity: '', value: '', upperValue: '' })}>
            {offeredKinds.map((kind) => <option key={kind} value={kind}>{KIND_LABELS[kind]}</option>)}
          </select></label>
          <label>Uploaded field<select value={route.field} onChange={(e) => updateRoute(index, { field: e.target.value, value: '', upperValue: '' })}>
            <option value="">Choose a real column</option>{profile.fields.filter((field) => route.kind !== 'prefix_search' || field.type === 'string')
              .map((field) => <option key={field.name} value={field.name}>{field.source_name ?? field.name}</option>)}
          </select></label>
          <label>Relative traffic weight<input type="number" min="0.000001" step="any" value={route.weight}
            onChange={(e) => updateRoute(index, { weight: e.target.value })}/></label>
          <label>{route.kind === 'range_scan' ? 'Range lower bound' : route.kind === 'prefix_search' ? 'Prefix to search' : 'Value to find'}
            <input list={'csv-observed-values-' + index} value={route.value}
              onChange={(e) => updateRoute(index, { value: e.target.value })} placeholder="Enter or select a real uploaded value"/>
            <datalist id={'csv-observed-values-' + index}>{observedValues(route.field).map((value) =>
              <option key={value} value={value}/>)}</datalist>
            <small>Suggested values come only from the current visible page of your uploaded data. You can type any value.</small>
          </label>
          {route.kind === 'range_scan' && <label>Range upper bound
            <input value={route.upperValue} onChange={(e) => updateRoute(index, { upperValue: e.target.value })}/></label>}
          {isSelectivityKind(route.kind) && <label>Selectivity (0–1), measured or provided
            <input type="number" min="0" max="1" step="any" value={route.selectivity}
              onChange={(e) => updateRoute(index, { selectivity: e.target.value })}
              placeholder="Run actual query to measure"/></label>}
          {(['point_lookup', 'range_scan', 'filter', 'prefix_search'] as Kind[]).includes(route.kind) ?
            <button className="secondary-button" disabled={probeBusy !== null || !route.field}
              onClick={() => void probeRoute(index)}>{probeBusy === index ? 'Scanning…' : 'Query real records using C++'}</button> :
            <small>Write frequency is a declared workload assumption, not a measured mutation. Importing and inspecting a dataset never changes its records.</small>}
          {routes.length > 1 && <button className="csv-remove" onClick={() => {
            setRoutes((items) => items.filter((_, i) => i !== index))
            setResult(null); setOptions([]); setArtifact(null)
          }}>Remove operation</button>}
          {route.observed && <div className="csv-probe">
            <strong>Measured against uploaded records: {fmt(route.observed.matched_records, 0)} of {fmt(route.observed.total_records, 0)} matched ({fmt(route.observed.matched_selectivity * 100, 3)}%)</strong>
            <small>{route.observed.evidence}. This is a full reference scan, not a benchmark of the selected index.</small>
            <div className="csv-table-scroll"><table><thead><tr><th>Source row</th>{route.observed.source_columns.map((name, i) => <th key={i}>{name}</th>)}</tr></thead>
              <tbody>{route.observed.preview_records.map((record) => <tr key={record.record_index}><td>{record.record_index}</td>
                {record.values.map((value, i) => <td key={i}>{value}</td>)}</tr>)}</tbody></table></div>
            {route.observed.preview_truncated && <small>Displaying the first 20 matches; the count includes all matching records.</small>}
            {isSelectivityKind(route.kind) && route.observed.matched_selectivity === 0 && <small>No rows match this predicate. Choose a matching predicate or explicitly describe an anticipated workload; zero selectivity is not an accepted positive model input.</small>}
          </div>}
        </div>)}
        <div className="csv-actions">
          <button className="secondary-button" disabled={routes.length >= 32}
            onClick={() => setRoutes((old) => [...old, blankRoute()])}>Add another operation</button>
        </div>
        <div className="csv-constraints">
          <label>Index memory budget (MB)<input type="number" step="any" min="0" placeholder="Unbounded"
            value={memoryMb} onChange={(e) => { setMemoryMb(e.target.value); invalidateDecision() }}/></label>
          <label>Estimated updates / second<input type="number" step="any" min="0" value={updateRate}
            onChange={(e) => { setUpdateRate(e.target.value); invalidateDecision() }}/></label>
          <label>Search strategy<select value={strategy} onChange={(e) => { setStrategy(e.target.value as SearchStrategy); invalidateDecision() }}>
            <option value="auto">Auto (exhaustive where feasible, otherwise beam)</option>
            <option value="exhaustive">Bounded exhaustive</option><option value="beam">Beam search</option>
            <option value="greedy">Greedy</option></select></label>
          <label>Maximum evaluated candidates<input type="number" min="1" max="10000" step="1" value={candidateBudget}
            onChange={(e) => { setCandidateBudget(e.target.value); invalidateDecision() }}/></label>
        </div>
        <h3>Optimize for what?</h3>
        <div className="csv-constraints">
          {(['latency','memory','update','build'] as const).map((key) => <label key={key}>{key} objective weight
            <input type="number" min="0" step="any" value={objectives[key]} onChange={(e) => {
              setObjectives((current) => ({ ...current, [key]: e.target.value })); invalidateDecision()
            }}/></label>)}
        </div>
        <small>The engine ranks only plans it evaluated. A lower memory budget can reject otherwise fast candidates; changing weights and predicates can change the ranking. No claim of globally optimal performance is made when search is truncated.</small>
        <div className="csv-actions">
          <button className="primary-button" disabled={busy} onClick={() => void runOptimization()}>
            {busy ? 'Evaluating…' : 'Search and compare actual DSA candidates'}</button>
          <button className="secondary-button" onClick={openWorkbench}>Open this dataset's editable MWS</button>
        </div>
      </section>}
      {error && <p className="csv-error" role="alert">{error}</p>}
      {result && <section className="csv-step csv-result">
        <h2>5 · Full comparison and selection evidence</h2>
        {result.winner ? <><p><strong>Best feasible evaluated plan:</strong> {result.winner.unique_primitives.join(' + ')}</p>
          <p>Modeled latency {fmt(result.winner.predicted_latency_us)} μs · modeled index memory {fmt(result.winner.predicted_memory_mb, 5)} MB · score {fmt(result.winner.score, 5)}</p>
        </> : <p>No evaluated configuration fits the declared constraints. The optimizer did not fabricate a winner.</p>}
        {result.search_summary && <p><strong>{fmt(result.search_summary.evaluated_configurations, 0)}</strong> evaluated of <strong>{fmt(result.search_summary.theoretical_configurations, 0)}</strong> theoretical plans · <strong>{fmt(result.search_summary.feasible_configurations, 0)}</strong> feasible · strategy {result.search_summary.strategy}{result.search_summary.truncated ? ' · search truncated' : ' · all configurations evaluated'}</p>}
        <p><strong>Evidence:</strong> {result.evidence_state}. Candidate latencies are predictions, not measured performance on the uploaded file.</p>
        <h3>Eligibility for every operation (all registered structures)</h3>
        {options.map((item) => <div key={item.query_index} className="csv-eligibility">
          <strong>Query {item.query_index + 1} · {item.kind} · {item.field}</strong>
          <div className="csv-option-grid">{item.choices.map((choice) => <div key={choice.primitive}
            className={'csv-option ' + (choice.eligible ? 'csv-eligible' : 'csv-ineligible')}>
            <strong>{choice.display_name}</strong><small>{choice.eligible ? 'Eligible for native search' : choice.reason}</small>
          </div>)}</div>
        </div>)}
        <h3>Best evaluated alternatives by real index type</h3>
        <p>These are the lowest-scoring <strong>feasible evaluated</strong> configurations containing each structure.
          Different memory limits, field types, operation mixes and search budgets can change which structures are eligible and which plans rank highest.
          An index missing below was not present in a feasible evaluated plan; this is not proof it can never work.</p>
        {distinctAlternatives.length ? <div className="csv-table-scroll"><table>
          <thead><tr><th>Structure in plan</th><th>Feasible evaluated plans</th><th>Lowest modeled score</th><th>Predicted index memory</th><th>Best candidate ID</th></tr></thead>
          <tbody>{distinctAlternatives.map(({ primitive, best, count }) => <tr key={primitive}>
            <td><strong>{catalog.find((entry) => entry.id === primitive)?.name ?? primitive}</strong></td>
            <td>{fmt(count, 0)}</td><td>{best ? fmt(best.score, 5) : '—'}</td>
            <td>{best ? fmt(best.predicted_memory_mb, 5) + ' MB' : '—'}</td><td><code>{best?.id ?? '—'}</code></td>
          </tr>)}</tbody>
        </table></div> : <p>No feasible candidates were evaluated under these constraints.</p>}
        <small>Selection is model-based, not an on-file benchmark. The catalog above shows all registered implementations;
          per-operation eligibility includes rejected index types and explicit reasons.</small>
        <h3>All evaluated candidates (ranked, including rejected)</h3>
        <div className="csv-table-scroll"><table><thead><tr><th>Rank</th><th>Configuration (operation → index)</th><th>Predicted latency μs</th><th>Index MB</th><th>Modeled score</th><th>Feasibility / rejection</th></tr></thead>
          <tbody>{shown?.map((candidate, index) => <tr key={candidate.id}>
            <td>{index + 1}</td><td>{candidate.assignments.map((a) => (
              <div key={a.query_index}><small>{a.query_kind} ({a.field ?? '—'}) → <strong>{a.primitive}</strong></small></div>
            ))}</td>
            <td>{fmt(candidate.predicted_latency_us, 5)}</td>
            <td>{fmt(candidate.predicted_memory_mb, 5)}</td>
            <td>{fmt(candidate.score, 5)}</td>
            <td>{candidate.feasible ? 'Eligible' : candidate.rejection_reasons.join('; ')}</td>
          </tr>)}</tbody></table></div>
        {(result.candidates.length > 25) && <button className="secondary-button" onClick={() => setShowAll((now) => !now)}>
          {showAll ? 'Show top 25' : 'Show all ' + fmt(result.candidates.length, 0) + ' evaluated candidates'}
        </button>}
        <div className="csv-actions"><button className="secondary-button" onClick={() => downloadText(
          'morpheus_candidates.json', JSON.stringify({ input_sha256: profile?.source_sha256, spec_hash: result.spec_hash,
            search: result.search_summary, candidates: result.candidates, evidence: result.evidence_state }, null, 2)
        )}>Export real candidate comparison (JSON)</button></div>
        {result.explanation.map((line, i) => <p key={i} className="csv-explanation">{line}</p>)}
        {result.warnings.map((line, i) => <p key={i} className="csv-warning">{line}</p>)}
      </section>}
      {(artifact || codeError) && <section className="csv-step">
        <h2>6 · Generate the selected C++ physical plan</h2>
        {artifact && <><p><strong>{artifact.file_name}</strong> · {artifact.language} · candidate {artifact.candidate_id}</p>
          <p>This is a real generated header built from the chosen schema and index assignments. It is <strong>not compile-verified or benchmarked by this button</strong>; compile and differential-test it with the repository's C++ library before claiming correctness.</p>
          <div className="csv-actions"><button className="primary-button"
            onClick={() => downloadText(artifact.file_name, artifact.source)}>Download generated C++ header</button></div>
          <details><summary>Inspect generated C++ source</summary><pre className="csv-code">{artifact.source}</pre></details>
          <small>{artifact.status} · {artifact.requires}</small>
        </>}
        {codeError && <p className="csv-warning">This plan could not be emitted as a standalone C++ header: {codeError}. The optimizer's result remains a modeled recommendation.</p>}
      </section>}
    </section>
  </main>
}
