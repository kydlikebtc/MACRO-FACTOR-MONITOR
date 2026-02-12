import { useState, useEffect } from 'react'
import { useReport } from './hooks/useReport'
import { getLatestFactors } from './api/client'
import type { FactorReading } from './types'
import SignalHero from './components/SignalHero'
import FactorStrip from './components/FactorStrip'
import AgentCard from './components/AgentCard'
import SignalHistoryChart from './components/SignalHistoryChart'
import FactorTimeSeriesChart from './components/FactorTimeSeriesChart'
import RefreshButton from './components/RefreshButton'
import StatsFooter from './components/StatsFooter'

function HealthBar({ liveCount, totalCount }: { liveCount: number; totalCount: number }) {
  const pct = totalCount > 0 ? (liveCount / totalCount) * 100 : 0
  let color = 'var(--green-500)'
  if (pct <= 30) {
    color = 'var(--red-500)'
  } else if (pct <= 70) {
    color = 'var(--amber-500)'
  }

  return (
    <div className="health-row">
      DATA HEALTH
      <div className="health-bar">
        <div className="health-fill" style={{ width: `${pct.toFixed(0)}%`, background: color }} />
      </div>
      <span>{liveCount}/{totalCount} live</span>
    </div>
  )
}

const formatTime = (d: Date) =>
  d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

export default function App() {
  const { report, loading, error, refresh } = useReport()
  const [factorMeta, setFactorMeta] = useState<Record<string, FactorReading>>({})
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    getLatestFactors().then(setFactorMeta).catch(() => {})
  }, [report])

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  if (loading && !report) {
    return (
      <>
        <div className="topbar" />
        <div className="container">
          <div className="loading-container">
            <div className="loading-spinner" />
            <div className="loading-text">Loading Report...</div>
          </div>
        </div>
      </>
    )
  }

  if (error && !report) {
    return (
      <>
        <div className="topbar" />
        <div className="container">
          <div className="error-container">
            <div className="error-icon">!</div>
            <div className="error-message">{error}</div>
            <button className="error-retry" onClick={refresh}>
              Retry
            </button>
          </div>
        </div>
      </>
    )
  }

  if (!report) {
    return null
  }

  const totalData = report.live_data_points + report.fallback_data_points
  const currentTs = formatTime(now)

  return (
    <>
      <div className="topbar" />
      <div className="container">
        {/* Header */}
        <div className="header">
          <div className="header-left">
            <h1>MACRO FACTOR MONITOR</h1>
            <div className="subtitle">
              US Equity Multi-Factor Dashboard &mdash; Agent Swarm v3.0
            </div>
          </div>
          <div className="header-right">
            <div className="ts">{currentTs}</div>
            <HealthBar liveCount={report.live_data_points} totalCount={totalData} />
          </div>
        </div>

        {/* Signal Hero */}
        <SignalHero
          signal={report.overall_signal}
          weightedScore={report.weighted_score}
          bullCount={report.bull_count}
          neutralCount={report.neutral_count}
          bearCount={report.bear_count}
        />

        {/* Factor Strip */}
        <FactorStrip
          bullFactors={report.bull_factors}
          neutralFactors={report.neutral_factors}
          bearFactors={report.bear_factors}
        />

        {/* Agent Cards */}
        {report.agents.map((agent) => (
          <AgentCard key={agent.name} agent={agent} factorMeta={factorMeta} />
        ))}

        {/* Charts */}
        <div className="charts-section">
          <SignalHistoryChart />
          <FactorTimeSeriesChart />
        </div>

        {/* Footer */}
        <StatsFooter
          timestamp={report.timestamp}
          liveDataPoints={report.live_data_points}
          fallbackDataPoints={report.fallback_data_points}
        />
      </div>

      {/* Refresh FAB */}
      <RefreshButton onComplete={refresh} />
    </>
  )
}
