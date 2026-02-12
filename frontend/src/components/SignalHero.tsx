import type { Signal } from '../types'

interface SignalHeroProps {
  signal: Signal
  weightedScore: number
  bullCount: number
  neutralCount: number
  bearCount: number
}

const SIGNAL_CONFIG: Record<Signal, {
  color: string
  bg: string
  label: string
  desc: string
}> = {
  BULLISH: {
    color: '#0d7340',
    bg: '#e6f4ed',
    label: 'BULLISH',
    desc: '\u591a\u5934\u4e3b\u5bfc \u2014 \u5b8f\u89c2\u73af\u5883\u504f\u591a',
  },
  BEARISH: {
    color: '#c41e3a',
    bg: '#fce8ec',
    label: 'BEARISH',
    desc: '\u7a7a\u5934\u4e3b\u5bfc \u2014 \u5b8f\u89c2\u73af\u5883\u504f\u7a7a',
  },
  NEUTRAL: {
    color: '#b8860b',
    bg: '#fdf6e3',
    label: 'NEUTRAL',
    desc: '\u591a\u7a7a\u5747\u8861 \u2014 \u65e0\u660e\u786e\u65b9\u5411\u6027\u4fe1\u53f7',
  },
}

export default function SignalHero({
  signal,
  weightedScore,
  bullCount,
  neutralCount,
  bearCount,
}: SignalHeroProps) {
  const config = SIGNAL_CONFIG[signal]
  const scorePct = Math.max(0, Math.min(100, (weightedScore + 1) / 2 * 100))

  const heroStyle: React.CSSProperties = {
    background: config.bg,
    border: `1px solid ${config.color}30`,
    borderLeft: `5px solid ${config.color}`,
  }

  return (
    <div className="signal-hero" style={heroStyle}>
      <div className="signal-hero-left">
        <div>
          <div className="signal-hero-label">COMPOSITE SIGNAL</div>
          <div className="signal-hero-value" style={{ color: config.color }}>
            {config.label}
          </div>
          <div className="signal-hero-desc">{config.desc}</div>
        </div>
      </div>
      <div className="signal-hero-right">
        <div className="signal-score-label">WEIGHTED SCORE</div>
        <div className="score-bar-container">
          <div className="score-bar-bg" />
          <div
            className="score-bar-indicator"
            style={{
              left: `${scorePct.toFixed(1)}%`,
              background: config.color,
            }}
          />
        </div>
        <div className="score-value" style={{ color: config.color }}>
          {weightedScore >= 0 ? '+' : ''}{weightedScore.toFixed(3)}
        </div>
        <div className="score-votes">
          <span className="vote-bull">Bull {bullCount}</span>
          <span className="vote-dot">&bull;</span>
          <span className="vote-neutral">Neutral {neutralCount}</span>
          <span className="vote-dot">&bull;</span>
          <span className="vote-bear">Bear {bearCount}</span>
        </div>
      </div>
    </div>
  )
}
