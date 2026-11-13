import { useEffect, useState } from 'react'
import { ApiError } from '../../../api/errors'

type LoadState<T> = { key: string; status: 'loading' } | { key: string; status: 'success'; data: T } | { key: string; status: 'error'; error: unknown }
export function useConsulta<T>(key: string, load: (signal: AbortSignal) => Promise<T>) {
  const [result, setResult] = useState<LoadState<T>>({ key: '', status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let active = true
    void load(controller.signal).then(data => {
      if (active && !controller.signal.aborted) setResult({ key, status: 'success', data })
    }).catch(error => {
      if (active && !controller.signal.aborted && !(error instanceof ApiError && error.kind === 'cancelled')) {
        setResult({ key, status: 'error', error })
      }
    })
    return () => { active = false; controller.abort() }
  }, [key, load, attempt])
  // New queries never render the previous page while their effect starts.
  const current: LoadState<T> = result.key === key ? result : { key, status: 'loading' }
  return { result: current, retry: () => { setResult({ key: '', status: 'loading' }); setAttempt(n => n + 1) } }
}
