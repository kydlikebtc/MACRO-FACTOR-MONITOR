import { useState, useEffect, useCallback } from 'react'
import type { Report } from '../types'
import { getLatestReport } from '../api/client'

export function useReport(pollInterval = 60000) {
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await getLatestReport()
      setReport(data)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, pollInterval)
    return () => clearInterval(timer)
  }, [refresh, pollInterval])

  return { report, loading, error, refresh }
}
