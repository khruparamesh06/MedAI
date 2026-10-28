import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'
import { ApiError } from '../api/client'

export interface ApiState<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
  setData: (value: T) => void
}

/** Loads data on mount and whenever `deps` change; ignores responses from stale requests. */
export function useApi<T>(loader: () => Promise<T>, deps: DependencyList = []): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const requestId = useRef(0)

  // A data-fetching hook necessarily sets loading state when a new request starts, and `deps` is the
  // caller's dependency list for `loader` (same contract as useEffect), so these two rules are relaxed here.
  /* eslint-disable react/set-state-in-effect, react-hooks/exhaustive-deps */
  useEffect(() => {
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    loader()
      .then((value) => { if (id === requestId.current) setData(value) })
      .catch((err: unknown) => {
        if (id === requestId.current) setError(err instanceof ApiError ? err : new ApiError(0, String(err)))
      })
      .finally(() => { if (id === requestId.current) setLoading(false) })
  }, [...deps, tick])
  /* eslint-enable react/set-state-in-effect, react-hooks/exhaustive-deps */

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload, setData }
}

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Something went wrong.'
}
