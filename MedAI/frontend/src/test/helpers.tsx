import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AppRoutes } from '../App'
import { AuthProvider } from '../hooks/useAuth'
import { ToastProvider } from '../hooks/useToast'

type Handler = (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined

/** Replace fetch with a router of fake API responses. Unmatched requests fail loudly. */
export function mockApi(handler: Handler) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    const res = handler(url, init)
    if (!res) throw new Error(`Unmocked request: ${init?.method ?? 'GET'} ${url}`)
    return new Response(res.body === undefined ? null : JSON.stringify(res.body), {
      status: res.status ?? 200,
      headers: { 'content-type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
}

export const patientUser = {
  id: 5, email: 'patient@example.com', full_name: 'Demo Patient', role: 'patient', status: 'active',
  date_of_birth: null, sex: null, phone: null, must_change_password: false, created_at: '2026-01-01T00:00:00Z',
}

export const emptyPage = { items: [], total: 0, limit: 20, offset: 0 }
