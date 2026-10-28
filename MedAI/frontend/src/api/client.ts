/**
 * Minimal fetch wrapper for the MedAI API.
 *
 * Token strategy: the short-lived JWT access token is kept in sessionStorage (cleared when the
 * tab closes) and sent as `Authorization: Bearer ...`. No cookies are used, so CSRF does not
 * apply; XSS is mitigated by React's escaping and by never rendering HTML from the API.
 * See docs/ARCHITECTURE.md for the trade-offs.
 */
export const API_URL = (
  (import.meta.env.VITE_API_URL as string | undefined) ||
  'https://medai-backend-ywhc.onrender.com'
).replace(/\/$/, '')

const TOKEN_KEY = 'medai.token'

export const tokenStore = {
  get: (): string | null => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
}

export class ApiError extends Error {
  status: number
  fieldErrors: Record<string, string>

  constructor(status: number, message: string, fieldErrors: Record<string, string> = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

/** Fired when the server rejects the session so the app can return to the sign-in page. */
export const SESSION_EXPIRED_EVENT = 'medai:session-expired'

type ValidationItem = { loc?: (string | number)[]; msg?: string }

function parseError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return new ApiError(status, detail)
  if (Array.isArray(detail)) {
    const fieldErrors: Record<string, string> = {}
    for (const item of detail as ValidationItem[]) {
      const field = String(item.loc?.[item.loc.length - 1] ?? 'form')
      fieldErrors[field] = (item.msg ?? 'Invalid value').replace(/^Value error, /, '')
    }
    const first = Object.values(fieldErrors)[0]
    return new ApiError(status, first ? `Please check the form: ${first}` : 'Invalid request', fieldErrors)
  }
  return new ApiError(status, status >= 500 ? 'The server encountered an error. Please try again.' : `Request failed (${status})`)
}

export async function request<T>(path: string, options: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let body = options.body
  if (options.json !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.json)
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...options, headers, body })
  } catch {
    throw new ApiError(0, `Cannot reach the MedAI server at ${API_URL}. Is the backend running?`)
  }

  if (response.status === 401 && token) {
    tokenStore.clear()
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw parseError(response.status, data)
  }
  if (response.status === 204) return undefined as T
  const type = response.headers.get('content-type') ?? ''
  return (type.includes('application/json') ? response.json() : response.blob()) as Promise<T>
}
