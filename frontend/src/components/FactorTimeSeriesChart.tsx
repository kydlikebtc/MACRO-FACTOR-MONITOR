import { useState, useCallback } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { useFactorSeries } from '../hooks/useFactorSeries'

const DAY_OPTIONS = [7, 30, 90] as const

const FACTOR_KEYS: { key: string; label: string }[] = [
  { key: 'WALCL', label: 'Fed\u8d44\u4ea7\u8d1f\u503a\u8868 (WALCL)' },
  { key: 'TGA', label: '\u8d22\u653f\u90e8TGA' },
  { key: 'RRP', label: '\u9006\u56de\u8d2d RRP' },
  { key: 'Net Liquidity', label: '\u51c0\u6d41\u52a8\u6027' },
  { key: 'TTM PE', label: 'S&P 500 TTM PE' },
  { key: 'Forward PE', label: 'S&P 500 Forward PE' },
  { key: '10Y Yield', label: '10Y\u56fd\u503a\u6536\u76ca\u7387' },
  { key: 'ERP', label: '\u80a1\u6743\u98ce\u9669\u6ea2\u4ef7 ERP' },
  { key: 'VIX', label: 'VIX\u6ce2\u52a8\u7387' },
  { key: 'HY OAS', label: 'HY\u4fe1\u7528\u5229\u5dee' },
  { key: 'Yield Curve', label: '10Y-2Y\u5229\u5dee' },
  { key: 'DXY', label: '\u7f8e\u5143\u6307\u6570 DXY' },
]

interface ChartDataPoint {
  date: string
  value: number
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
      <div className="tooltip-value">{value.toFixed(2)}</div>
    </div>
  )
}

export default function FactorTimeSeriesChart() {
  const [selectedKey, setSelectedKey] = useState<string>(FACTOR_KEYS[0].key)
  const [days, setDays] = useState<number>(30)
  const { series, loading } = useFactorSeries(selectedKey, days)

  const handleDayChange = useCallback((d: number) => {
    setDays(d)
  }, [])

  const handleKeyChange = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedKey(e.target.value)
  }, [])

  // 按天聚合：同一天取最后一条记录的 value
  const chartData: ChartDataPoint[] = (() => {
    const dayMap = new Map<string, number>()
    for (const point of series) {
      const d = new Date(point.fetched_at)
      const key = `${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')}`
      dayMap.set(key, point.value)
    }
    return Array.from(dayMap.entries()).map(([date, value]) => ({ date, value }))
  })()

  return (
    <div className="chart-card">
      <div className="chart-header">
        <span className="chart-title">Factor Trend</span>
        <div className="chart-controls">
          <select value={selectedKey} onChange={handleKeyChange}>
            {FACTOR_KEYS.map((fk) => (
              <option key={fk.key} value={fk.key}>
                {fk.label}
              </option>
            ))}
          </select>
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
            <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
              <defs>
                <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef0f4" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#8b919e' }}
                tickLine={false}
                axisLine={{ stroke: '#e2e5ea' }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#8b919e' }}
                tickLine={false}
                axisLine={{ stroke: '#e2e5ea' }}
                width={52}
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => {
                  if (Math.abs(v) >= 1000) {
                    return `${(v / 1000).toFixed(1)}k`
                  }
                  return v.toFixed(1)
                }}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#2563eb"
                strokeWidth={2}
                fill="url(#areaFill)"
                dot={false}
                activeDot={{ r: 4, fill: '#2563eb', strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
