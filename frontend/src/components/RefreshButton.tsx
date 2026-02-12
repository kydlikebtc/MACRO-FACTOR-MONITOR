import { useState, useCallback, useRef } from 'react'
import { triggerRun, getRunStatus } from '../api/client'

interface RefreshButtonProps {
  onComplete: () => void
}

export default function RefreshButton({ onComplete }: RefreshButtonProps) {
  const [running, setRunning] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const handleClick = useCallback(async () => {
    if (running) return

    setRunning(true)
    try {
      const result = await triggerRun()
      if (result.status === 'already_running' || result.status === 'started' || result.status === 'running') {
        pollingRef.current = setInterval(async () => {
          try {
            const status = await getRunStatus()
            if (status.status === 'idle') {
              stopPolling()
              setRunning(false)
              onComplete()
            }
          } catch {
            stopPolling()
            setRunning(false)
          }
        }, 3000)
      } else {
        setRunning(false)
        onComplete()
      }
    } catch {
      setRunning(false)
    }
  }, [running, onComplete, stopPolling])

  return (
    <button
      className={`refresh-btn${running ? ' spinning' : ''}`}
      onClick={handleClick}
      disabled={running}
      title={running ? 'Running...' : 'Refresh data'}
      aria-label={running ? 'Running analysis' : 'Trigger data refresh'}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 2v6h-6" />
        <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
        <path d="M3 22v-6h6" />
        <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      </svg>
    </button>
  )
}
