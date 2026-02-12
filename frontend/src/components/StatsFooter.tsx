interface StatsFooterProps {
  timestamp: string
  liveDataPoints: number
  fallbackDataPoints: number
}

export default function StatsFooter({
  timestamp,
  liveDataPoints,
  fallbackDataPoints,
}: StatsFooterProps) {
  const formattedTs = new Date(timestamp).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })

  return (
    <div className="footer">
      <span>MACRO FACTOR SWARM V3.0 &mdash; AGENT SWARM + SQLITE PERSISTENCE</span>
      <span>
        {liveDataPoints} LIVE + {fallbackDataPoints} CACHED &mdash; {formattedTs}
      </span>
    </div>
  )
}
