export type Signal = 'BULLISH' | 'BEARISH' | 'NEUTRAL'

export interface Factor {
  name: string
  name_en: string
  value: number
  unit: string
  signal: Signal
  source_name: string
  source_url: string
  interpretation: string
  is_live: boolean
}

export interface AgentResult {
  name: string
  category: string
  signal: Signal
  confidence: number
  summary: string | null
  formula: string | null
  error: string | null
  factors: Factor[]
}

export interface Report {
  timestamp: string
  overall_signal: Signal
  weighted_score: number
  bull_count: number
  neutral_count: number
  bear_count: number
  bull_factors: string[]
  neutral_factors: string[]
  bear_factors: string[]
  live_data_points: number
  fallback_data_points: number
  agents: AgentResult[]
}

export interface SignalHistoryEntry {
  overall_signal: Signal
  weighted_score: number
  live_count: number
  fallback_count: number
  created_at: string
}

export interface TimeSeriesPoint {
  value: number
  fetched_at: string
  is_live: number
  fetch_method: string
}

export interface SourceHealth {
  fetch_method: string
  total: number
  successes: number
  avg_latency_ms: number | null
  success_rate: number
}

export interface DBStats {
  factor_readings: number
  report_snapshots: number
  source_health: number
  cache_metadata: number
}

export interface FactorReading {
  factor_key: string
  value: number
  unit: string
  signal: Signal
  is_live: boolean
  source_name: string
  source_url: string
  fetch_method: string
  fetched_at: string
}

export interface RunStatus {
  status: 'idle' | 'running' | 'started' | 'already_running'
  message: string
}
