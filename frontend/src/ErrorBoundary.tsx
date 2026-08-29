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
        <div className="morpheus-fatal-ambient morpheus-fatal-ambient--cyan" aria-hidden="true" />
        <div className="morpheus-fatal-ambient morpheus-fatal-ambient--violet" aria-hidden="true" />
        <section className="morpheus-fatal-card">
          <div className="morpheus-fatal-logo" aria-hidden="true" />
          <div className="morpheus-fatal-kicker">RECOVERABLE INTERFACE FAILURE</div>
          <h1>MORPHEUS protected the workspace.</h1>
          <p>
            The interface hit an unexpected render error. Engine state is not silently changed by this screen.
            Retry the UI first; reload only if the same component fails again.
          </p>
          <div className="morpheus-fatal-details">
            <span>Error fingerprint</span>
            <code>{errorId}</code>
            <span>Type</span>
            <code>{error.name}</code>
          </div>
          <div className="morpheus-fatal-actions">
            <button onClick={this.retry}>Retry interface</button>
            <button className="secondary" onClick={this.reload}>Reload MORPHEUS</button>
          </div>
          <details>
            <summary>Technical detail</summary>
            <pre>{error.message}</pre>
          </details>
          <small>
            This boundary catches React render/lifecycle failures. Backend, generated-code and research failures remain governed by their own evidence and rollback gates.
          </small>
        </section>
      </main>
    )
  }
}
