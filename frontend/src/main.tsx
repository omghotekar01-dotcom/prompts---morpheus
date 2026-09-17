import ReactDOM from 'react-dom/client'
import ErrorBoundary from './ErrorBoundary'
import StartupGate from './StartupGate'
import ThemeToggle from './ThemeToggle'
import './startup.css'
import './product.css'

const root = document.getElementById('root')
if (!root) {
  throw new Error('MORPHEUS root element is missing from the document')
}

ReactDOM.createRoot(root).render(
  <ErrorBoundary>
    <ThemeToggle />
    <StartupGate />
  </ErrorBoundary>
)
