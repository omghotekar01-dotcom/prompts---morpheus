import { Component, type ErrorInfo, type ReactNode } from 'react'
import './error-boundary.css'

type Props = { children: ReactNode }
type State = { error: Error | null; errorId: string | null }

function fingerprint(error: Error) {
  const source = `${error.name}:${error.message}:${error.stack ?? ''}`
  let hash = 2166136261
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return `UI-${(hash >>> 0).toString(16).padStart(8, '0').toUpperCase()}`
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, errorId: null }

  static getDerivedStateFromError(error: Error): State {
    return { error, errorId: fingerprint(error) }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('MORPHEUS UI boundary captured an unhandled render failure', {
      errorId: fingerprint(error),
      error,
      componentStack: info.componentStack
    })
  }

  private retry = () => {
    this.setState({ error: null, errorId: null })
  }

  private reload = () => {
    window.location.reload()
  }

  render() {
    const { error, errorId } = this.state
    if (!error) return this.props.children

    return (
      <main className="morpheus-fatal" role="alert" aria-live="assertive">
        <section className="morpheus-fatal-card">
          <div className="morpheus-fatal-logo" aria-hidden="true" />
          <div className="morpheus-fatal-kicker">INTERFACE ERROR</div>
          <h1>The workspace view could not load.</h1>
          <p>
            MORPHEUS stopped rendering this view after an unexpected interface error. This recovery screen does not
            run synthesis, migration, activation or other engine actions.
          </p>
          <div className="morpheus-fatal-details">
            <span>Error fingerprint</span>
            <code>{errorId}</code>
            <span>Type</span>
            <code>{error.name}</code>
          </div>
          <div className="morpheus-fatal-actions">
            <button onClick={this.retry}>Try again</button>
            <button className="secondary" onClick={this.reload}>Reload app</button>
          </div>
          <details>
            <summary>Technical detail</summary>
            <pre>{error.message}</pre>
          </details>
          <small>
            Error ID {errorId} can be used when reporting the issue. Backend and evidence failures remain governed by their own explicit gates.
          </small>
        </section>
      </main>
    )
  }
}
