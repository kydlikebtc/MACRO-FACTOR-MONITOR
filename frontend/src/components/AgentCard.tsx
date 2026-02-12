import type { AgentResult, Factor, FactorReading, Signal } from '../types'

interface AgentCardProps {
  agent: AgentResult
  factorMeta?: Record<string, FactorReading>
}

const CATEGORY_META: Record<string, { en: string; cls: string }> = {
  '\u6d41\u52a8\u6027': { en: 'LIQUIDITY', cls: 'liq' },
  '\u4f30\u503c': { en: 'VALUATION', cls: 'val' },
  '\u98ce\u9669\u4e0e\u60c5\u7eea': { en: 'RISK / SENTIMENT', cls: 'risk' },
  '\u98ce\u9669': { en: 'RISK', cls: 'risk' },
  '\u60c5\u7eea': { en: 'SENTIMENT', cls: 'risk' },
}

const SIGNAL_CSS: Record<Signal, string> = {
  BULLISH: 'sig-bull',
  BEARISH: 'sig-bear',
  NEUTRAL: 'sig-neutral',
}

function ExternalLinkIcon() {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 12 12"
      style={{ marginLeft: 3, verticalAlign: 'middle' }}
    >
      <path
        d="M3.5 3H2.5A1.5 1.5 0 001 4.5v5A1.5 1.5 0 002.5 11h5A1.5 1.5 0 009 9.5V8.5M7 1h4v4M11 1L5.5 6.5"
        stroke="currentColor"
        fill="none"
        strokeWidth="1.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function SourceLink({ name, url }: { name: string; url: string }) {
  if (!url) {
    return <span className="src-calc">{name}</span>
  }
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="src-link">
      {name}
      <ExternalLinkIcon />
    </a>
  )
}

function LiveBadge({ isLive }: { isLive: boolean }) {
  if (isLive) {
    return (
      <span className="badge-live">
        <span className="live-dot" />
        LIVE
      </span>
    )
  }
  return <span className="badge-cached">CACHED</span>
}

function formatFetchedAt(fetched_at?: string): string | null {
  if (!fetched_at) return null
  try {
    const d = new Date(fetched_at)
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
  } catch {
    return null
  }
}

function FactorRow({ factor, fetchedAt }: { factor: Factor; fetchedAt?: string }) {
  const sigCss = SIGNAL_CSS[factor.signal]
  const valDisplay = `${factor.value}${factor.unit}`
  const dateStr = formatFetchedAt(fetchedAt)

  return (
    <tr className="frow">
      <td>
        <div className="fname">{factor.name}</div>
        <div className="fname-en">{factor.name_en}</div>
      </td>
      <td className="fcol-val">
        {valDisplay}
        {dateStr && <div className="fcol-date">{dateStr}</div>}
      </td>
      <td className="fcol-sig">
        <span className={`${sigCss} sig-pill`}>{factor.signal}</span>
      </td>
      <td className="fcol-interp">
        <div>{factor.interpretation}</div>
      </td>
      <td className="fcol-src">
        <SourceLink name={factor.source_name} url={factor.source_url} />
        <br />
        <LiveBadge isLive={factor.is_live} />
      </td>
    </tr>
  )
}

export default function AgentCard({ agent, factorMeta }: AgentCardProps) {
  if (agent.error) {
    return null
  }

  const meta = CATEGORY_META[agent.category] ?? { en: agent.category.toUpperCase(), cls: 'other' }
  const sigCss = SIGNAL_CSS[agent.signal]
  const confidenceText = `${(agent.confidence * 100).toFixed(0)}%`

  return (
    <div className={`agent-section agent-${meta.cls}`}>
      <div className="agent-header">
        <div className="agent-label">
          <span className="agent-tag">{meta.en}</span>
          <span className="agent-cn">{agent.category}</span>
        </div>
        <div className="agent-signal-wrap">
          <span className={`${sigCss} sig-pill`}>{agent.signal}</span>
          <span className="agent-conf">{confidenceText}</span>
        </div>
      </div>

      {(agent.formula || agent.summary) && (
        <div className="agent-formula-bar">
          {agent.formula && <code>{agent.formula}</code>}
          {agent.summary && <span className="formula-result">{agent.summary}</span>}
        </div>
      )}

      {agent.factors.length > 0 && (
        <table className="ftable">
          <thead>
            <tr>
              <th style={{ width: 160 }}>INDICATOR</th>
              <th style={{ width: 100 }}>VALUE</th>
              <th style={{ width: 80 }}>SIGNAL</th>
              <th>INTERPRETATION</th>
              <th style={{ width: 170 }}>SOURCE</th>
            </tr>
          </thead>
          <tbody>
            {agent.factors.map((f) => (
              <FactorRow
                key={`${f.name_en}-${f.name}`}
                factor={f}
                fetchedAt={factorMeta?.[f.name_en]?.fetched_at}
              />
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
