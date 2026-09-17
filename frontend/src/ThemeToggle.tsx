import { useLayoutEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import './theme.css'

type Theme = 'light' | 'dark'

function initialTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem('morpheus-theme')
  if (stored === 'light' || stored === 'dark') return stored
  return 'light'
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme
    document.documentElement.style.colorScheme = theme
    window.localStorage.setItem('morpheus-theme', theme)
  }, [theme])

  const next = theme === 'dark' ? 'light' : 'dark'

  return (
    <div className="theme-dock" aria-label="Appearance">
      <button
        className="theme-toggle"
        type="button"
        aria-label={`Switch to ${next} mode`}
        title={`Switch to ${next} mode`}
        onClick={() => setTheme(next)}
      >
        <span className={`theme-toggle-track ${theme === 'dark' ? 'is-dark' : ''}`} aria-hidden="true">
          <span className="theme-toggle-thumb">
            {theme === 'dark' ? <Moon size={15} /> : <Sun size={15} />}
          </span>
        </span>
        <span className="theme-toggle-label">{theme === 'dark' ? 'Dark' : 'Light'}</span>
      </button>
    </div>
  )
}

export default ThemeToggle
