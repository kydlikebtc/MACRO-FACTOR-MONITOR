import type {
  Report,
  FactorReading,
  SignalHistoryEntry,
  TimeSeriesPoint,
  SourceHealth,
  DBStats,
  RunStatus,
} from '../types'

const BASE = ''

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`)
  if (!res.ok) throw new Error(`API Error: ${res.status} ${res.statusText}`)
  return res.json()
}

export async function getLatestReport(): Promise<Report> {
  return fetchJSON<Report>('/api/report/latest')
}

export async function getSignalHistory(days = 30): Promise<{ days: number; history: SignalHistoryEntry[] }> {
  return fetchJSON(`/api/report/history?days=${days}`)
}

export async function getFactorTimeSeries(key: string, days = 30): Promise<{ factor_key: string; days: number; series: TimeSeriesPoint[] }> {
  return fetchJSON(`/api/factors/${encodeURIComponent(key)}/history?days=${days}`)
}

export async function getLatestFactors(): Promise<Record<string, FactorReading>> {
  const data = await fetchJSON<{ factors: Record<string, FactorReading> }>('/api/factors/latest')
  return data.factors
}

export async function getHealth(hours = 24): Promise<{ hours: number; sources: SourceHealth[] }> {
  return fetchJSON(`/api/health?hours=${hours}`)
}

export async function getStats(): Promise<DBStats> {
  return fetchJSON<DBStats>('/api/stats')
}

export async function triggerRun(): Promise<RunStatus> {
  const res = await fetch(`${BASE}/api/run`, { method: 'POST' })
  return res.json()
}

export async function getRunStatus(): Promise<RunStatus> {
  return fetchJSON<RunStatus>('/api/run/status')
}
