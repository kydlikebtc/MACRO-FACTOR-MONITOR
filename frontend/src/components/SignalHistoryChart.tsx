import { useState, useCallback } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
  CartesianGrid,
} from 'recharts'
import { useSignalHistory } from '../hooks/useSignalHistory'

const DAY_OPTIONS = [7, 30, 90] as const

interface ChartDataPoint {
  date: string
  score: number
}

interface CustomTooltipProps {
  active?: boolean
  payload?: Array<{ value: number }>
  label?: string
}

function ChartTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null
  }
  const value = payload[0].value
  return (
    <div className="custom-tooltip">
      <div className="tooltip-label">{label}</div>
      <div className="tooltip-value">
        {value >= 0 ? '+' : ''}{value.toFixed(3)}
      </div>
    </div>
  )
}

export default function SignalHistoryChart() {
  const [days, setDays] = useState<number>(30)
  const { history, loading } = useSignalHistory(days)

  const handleDayChange = useCallback((d: number) => {
    setDays(d)
  }, [])

  // 按天聚合：同一天取最后一条记录的 score
  const chartData: ChartDataPoint[] = (() => {
    const dayMap = new Map<string, number>()
    for (const entry of history) {
      const d = new Date(entry.created_at)
      const key = `${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`
      dayMap.set(key, entry.weighted_score)
    }
    return Array.from(dayMap.entries()).map(([date, score]) => ({ date, score }))
  })()

  return (
    <div className="chart-card">
      <div className="chart-header">
        <span className="chart-title">Signal History</span>
        <div className="chart-controls">
          {DAY_OPTIONS.map((d) => (
            <button
              key={d}
              className={days === d ? 'active' : ''}
              onClick={() => handleDayChange(d)}
            >
              {d}D
            </button>
          ))}
        </div>
      </div>
      <div className="chart-body">
        {loading ? (
          <div className="chart-loading">Loading...</div>
        ) : chartData.length === 0 ? (
          <div className="chart-loading">No data</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" />
              <ReferenceArea y1={0.2} y2={1} fill="#dcfce7" fillOpacity={0.3} />
              <ReferenceArea y1={-1} y2={-0.2} fill="#fee2e2" fillOpacity={0.3} />
              <ReferenceArea y1={-0.2} y2={0.2} fill="#fef3c7" fillOpacity={0.15} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#8b919e' }}
                tickLine={false}
                axisLine={{ stroke: '#e2e5ea' }}
              />
              <YAxis
                domain={[-1, 1]}
                ticks={[-1, -0.5, 0, 0.5, 1]}
                tick={{ fontSize: 10, fill: '#8b919e' }}
                tickLine={false}
                axisLine={{ stroke: '#e2e5ea' }}
                width={36}
                tickFormatter={(v: number) => v.toFixed(1)}
              />
              <Tooltip content={<ChartTooltip />} />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#1a1e2c"
                strokeWidth={2}
                dot={{ r: 2, fill: '#1a1e2c' }}
                activeDot={{ r: 4, fill: '#1a1e2c', strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
