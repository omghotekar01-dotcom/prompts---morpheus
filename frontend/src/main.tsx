import ReactDOM from 'react-dom/client'
import ErrorBoundary from './ErrorBoundary'
import StartupGate from './StartupGate'
import './startup.css'

const root = document.getElementById('root')
if (!root) {
  throw new Error('MORPHEUS root element is missing from the document')
}

ReactDOM.createRoot(root).render(
  <ErrorBoundary>
    <StartupGate />
  </ErrorBoundary>
)
