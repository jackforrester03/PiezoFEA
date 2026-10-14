import { useEffect, useState } from 'react'
import { api, type Health } from './api/client'
import { ResponsePlot } from './components/ResponsePlot'
import { CrossSection } from './components/CrossSection'
import { ElectrodeEditor } from './components/ElectrodeEditor'
import { GeometryEditor } from './components/GeometryEditor'
import { RunPanel } from './components/RunPanel'
import { StudyPanel } from './components/StudyPanel'

function HealthBadge() {
  const [health, setHealth] = useState<Health | null>(null)
  const [down, setDown] = useState(false)
  useEffect(() => {
    api.health().then(setHealth, () => setDown(true))
  }, [])
  const ok = health?.cfs_ok
  const text = down ? 'backend unreachable' : !health ? 'checking…' : ok ? 'openCFS ready' : 'openCFS not found'
  return (
    <span className={`badge ${down || (health && !ok) ? 'bad' : ok ? 'good' : ''}`} title={health?.cfs_path ?? ''}>
      {text}
    </span>
  )
}

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <h1>PiezoFEA</h1>
        <span className="subtitle">2D axisymmetric piezoelectric FE · openCFS</span>
        <HealthBadge />
      </header>
      <div className="layout">
        <aside className="sidebar">
          <GeometryEditor />
          <ElectrodeEditor />
          <StudyPanel />
          <RunPanel />
        </aside>
        <main className="main">
          <section className="panel">
            <header className="panel-header">
              <h2>Cross-section (r–z)</h2>
            </header>
            <CrossSection />
          </section>
          <section className="panel">
            <header className="panel-header">
              <h2>Results</h2>
            </header>
            <ResponsePlot />
          </section>
        </main>
      </div>
    </div>
  )
}
