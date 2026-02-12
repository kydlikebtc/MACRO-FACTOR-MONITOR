import { useState, useEffect } from 'react'
import type { SignalHistoryEntry } from '../types'
import { getSignalHistory } from '../api/client'

export function useSignalHistory(days = 30) {
  const [history, setHistory] = useState<SignalHistoryEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getSignalHistory(days)
      .then(data => setHistory(data.history))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [days])

  return { history, loading }
}
