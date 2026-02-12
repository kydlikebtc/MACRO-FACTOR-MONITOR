import { useState, useEffect } from 'react'
import type { TimeSeriesPoint } from '../types'
import { getFactorTimeSeries } from '../api/client'

export function useFactorSeries(key: string | null, days = 30) {
  const [series, setSeries] = useState<TimeSeriesPoint[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!key) {
      setSeries([])
      return
    }
    setLoading(true)
    getFactorTimeSeries(key, days)
      .then(data => setSeries(data.series))
      .catch(() => setSeries([]))
      .finally(() => setLoading(false))
  }, [key, days])

  return { series, loading }
}
