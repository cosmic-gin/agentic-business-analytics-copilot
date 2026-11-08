import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BarChart3, ClipboardCheck, Database, PanelTop } from 'lucide-react'
import { Dashboard } from './pages/Dashboard'
import { Evaluations } from './pages/Evaluations'
import { api } from './services/api'
import type { Metadata, Mode } from './types'
import './style.css'

function App() {
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [mode, setMode] = useState<Mode>('demo')
  const [loadError, setLoadError] = useState('')
  const [evaluation, setEvaluation] = useState(location.hash === '#evaluations')

  useEffect(() => {
    const navigate = () => setEvaluation(location.hash === '#evaluations')
    window.addEventListener('hashchange', navigate)
    api<Metadata>('/metadata').then(data => {
      setMetadata(data)
      setMode(data.default_mode)
    }).catch(error => setLoadError(error instanceof Error ? error.message : 'Dataset unavailable.'))
    return () => window.removeEventListener('hashchange', navigate)
  }, [])

  return <div className="shell">
    <aside className="sidebar">
      <a href="#" className="brand"><span className="brand-mark"><BarChart3 size={23} /></span>
        <span>Delivery Intelligence<small>ANALYTICS COPILOT</small></span></a>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Workspace">
        <a href="#" aria-current={!evaluation ? 'page' : undefined}><PanelTop size={18} /> Investigation</a>
        <a href="#evaluations" aria-current={evaluation ? 'page' : undefined}><ClipboardCheck size={18} /> Evaluation</a>
      </nav>
      <div className="sidebar-footer"><Database size={17} /><span>SQLite analytics<small>Read-only workspace</small></span></div>
    </aside>
    <div className="workspace">
      <div className="topbar"><span><b>Workspace</b><span className="breadcrumb-separator"> / </span>{evaluation ? 'Evaluation' : 'Investigation'}</span>
        <label className="mode-control"><span className="mode-dot" /> <span className="sr-only">Planner mode</span>
          <select aria-label="Planner mode" value={mode} onChange={event => setMode(event.target.value as Mode)}>
            <option value="demo">Demo mode</option>
            <option value="llm" disabled={!metadata?.enabled_modes.includes('llm')}>
              {metadata?.llm_provider ? 'LLM mode · ' + (metadata.llm_provider === 'groq' ? 'Groq' : 'OpenAI') : 'LLM mode'}
            </option>
          </select></label>
      </div>
      <main>{evaluation ? <Evaluations key={mode} mode={mode} /> : <Dashboard metadata={metadata} mode={mode} loadError={loadError} />}</main>
    </div>
  </div>
}

createRoot(document.getElementById('root')!).render(<App />)
