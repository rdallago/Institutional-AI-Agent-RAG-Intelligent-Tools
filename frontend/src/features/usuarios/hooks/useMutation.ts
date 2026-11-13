import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../../../api/errors'

export function useMutation() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const alive = useRef(true)
  const pending = useRef<AbortController | null>(null)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; pending.current?.abort() }
  }, [])
  const run = useCallback(async <T,>(task: (signal: AbortSignal) => Promise<T>, success: (value: T) => void) => {
    if (pending.current || !alive.current) return
    const controller = new AbortController()
    pending.current = controller
    setBusy(true)
    setError(null)
    try {
      const value = await task(controller.signal)
      if (alive.current && !controller.signal.aborted) { success(value); return true }
    } catch (failure) {
      if (alive.current && !controller.signal.aborted && !(failure instanceof ApiError && failure.kind === 'cancelled')) { setError(failure); return false }
    } finally {
      if (alive.current && pending.current === controller) { setBusy(false); pending.current = null }
    }
  }, [])
  return { busy, error, run }
}
