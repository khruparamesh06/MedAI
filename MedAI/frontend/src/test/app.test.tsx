import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { emptyPage, mockApi, patientUser, renderApp } from './helpers'

const notConfigured = {
  available: false, state: 'not_configured', reason: 'No model is enabled.', model_name: null, model_version: null,
  backend: null, labels: [], score_type: null, score_description: null, weights_sha256: null, device: null, source: null,
}

function patientApi(extra: (url: string, init?: RequestInit) => { status?: number; body?: unknown } | undefined = () => undefined) {
  return mockApi((url, init) => {
    const custom = extra(url, init)
    if (custom) return custom
    if (url.endsWith('/api/health')) return { body: { status: 'ok', app: 'MedAI', environment: 'test', clinic_timezone: 'UTC' } }
    if (url.endsWith('/api/auth/me')) return { body: patientUser }
    if (url.includes('/api/xrays?')) return { body: emptyPage }
    if (url.includes('/api/appointments')) return { body: emptyPage }
    if (url.endsWith('/api/assignments/mine')) return { body: [] }
    if (url.endsWith('/api/ai/status')) return { body: notConfigured }
    return undefined
  })
}

describe('routing', () => {
  it('shows the sign-in page at /', async () => {
    mockApi((url) => (url.endsWith('/api/health') ? { body: { status: 'ok' } } : undefined))
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('redirects protected routes to sign-in when signed out', async () => {
    mockApi((url) => (url.endsWith('/api/health') ? { body: { status: 'ok' } } : undefined))
    renderApp('/admin/doctors')
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('renders a 404 page for unknown routes', () => {
    renderApp('/does-not-exist')
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('sends a patient away from admin pages', async () => {
    sessionStorage.setItem('medai.token', 'test-token')
    patientApi()
    renderApp('/admin')
    expect(await screen.findByRole('heading', { name: /Hello, Demo/ })).toBeInTheDocument()
  })
})

describe('sign-in integration', () => {
  it('posts credentials and opens the patient dashboard', async () => {
    const fetchMock = patientApi((url, init) =>
      url.endsWith('/api/auth/login') && init?.method === 'POST'
        ? { body: { access_token: 'abc', token_type: 'bearer', expires_in: 3600, user: patientUser } }
        : undefined)
    renderApp('/')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'patient@example.com')
    await user.type(screen.getByLabelText('Password'), 'DemoPass123!')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: /Hello, Demo/ })).toBeInTheDocument()
    const loginCall = fetchMock.mock.calls.find(([u]) => String(u).endsWith('/api/auth/login'))
    expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({ email: 'patient@example.com', password: 'DemoPass123!' })
    expect(sessionStorage.getItem('medai.token')).toBe('abc')
  })

  it('shows the server error message on failed login', async () => {
    mockApi((url) => {
      if (url.endsWith('/api/health')) return { body: { status: 'ok' } }
      if (url.endsWith('/api/auth/login')) return { status: 401, body: { detail: 'Incorrect email or password.' } }
      return undefined
    })
    renderApp('/')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'x@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
  })

  it('reports when the backend is unreachable', async () => {
    mockApi(() => { throw new TypeError('Failed to fetch') })
    renderApp('/')
    expect(await screen.findByText('Server unreachable')).toBeInTheDocument()
  })
})

describe('registration form', () => {
  it('validates before contacting the server', async () => {
    const fetchMock = mockApi(() => undefined)
    renderApp('/register')
    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByText('Enter your full name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('X-ray result page', () => {
  const xray = {
    id: 9, owner_id: 5, original_filename: 'chest.png', content_type: 'image/png', size_bytes: 2048, width: 512, height: 512,
    view_position: 'PA', patient_note: null, status: 'uploaded', created_at: '2026-10-01T10:00:00Z', latest_analysis: null,
    review_count: 0, owner: { id: 5, full_name: 'Demo Patient', email: 'patient@example.com' }, analyses: [], reviews: [],
  }

  it('shows "Model not configured" and no scores when no model is installed', async () => {
    sessionStorage.setItem('medai.token', 'test-token')
    patientApi((url) => {
      if (url.endsWith('/api/xrays/9')) return { body: xray }
      if (url.endsWith('/api/xrays/9/image')) return { status: 404, body: { detail: 'Not found' } }
      return undefined
    })
    renderApp('/patient/xrays/9')
    expect(await screen.findByText('Model not configured')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Run AI analysis/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('table', { name: /scores/i })).not.toBeInTheDocument()
  })

  it('shows a retryable error state when loading fails', async () => {
    sessionStorage.setItem('medai.token', 'test-token')
    patientApi((url) => (url.endsWith('/api/xrays/9') ? { status: 404, body: { detail: 'X-ray not found' } } : undefined))
    renderApp('/patient/xrays/9')
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('X-ray not found'))
    expect(screen.getByRole('button', { name: /Try again/ })).toBeInTheDocument()
  })

  it('renders model scores with their limitations when an analysis exists', async () => {
    sessionStorage.setItem('medai.token', 'test-token')
    const analysis = {
      id: 3, upload_id: 9, status: 'completed', model_name: 'TorchXRayVision DenseNet-121', model_version: 'densenet121-res224-all',
      weights_sha256: 'abc', score_type: 'op_norm_sigmoid', score_description: 'Uncalibrated scores. NOT probabilities.',
      findings: [{ label: 'Effusion', display_name: 'Pleural effusion', score: 0.62, above_operating_threshold: true }],
      preprocessing: { image_size: 224 }, error_message: null, duration_ms: 120, created_at: '2026-10-01T10:05:00Z',
    }
    patientApi((url) => {
      if (url.endsWith('/api/xrays/9')) return { body: { ...xray, status: 'analyzed', analyses: [analysis], latest_analysis: analysis } }
      if (url.endsWith('/api/xrays/9/image')) return { status: 404, body: { detail: 'Not found' } }
      return undefined
    })
    renderApp('/patient/xrays/9')
    expect(await screen.findByText('Pleural effusion')).toBeInTheDocument()
    expect(screen.getByText('0.62')).toBeInTheDocument()
    expect(screen.getByText(/does not estimate disease severity/)).toBeInTheDocument()
    expect(screen.getByText(/even one that is not a chest X-ray/)).toBeInTheDocument()
    expect(screen.getByText(/decision-support output only/)).toBeInTheDocument()
  })
})

describe('account security', () => {
  it('forces a user with a temporary password to the account page', async () => {
    sessionStorage.setItem('medai.token', 'test-token')
    const doctor = { ...patientUser, id: 9, role: 'doctor', full_name: 'Dr Temp', must_change_password: true }
    mockApi((url) => {
      if (url.endsWith('/api/auth/me')) return { body: doctor }
      if (url.endsWith('/api/health')) return { body: { status: 'ok', clinic_timezone: 'UTC' } }
      return undefined
    })
    renderApp('/doctor')
    expect(await screen.findByRole('heading', { name: 'Account settings' })).toBeInTheDocument()
    expect(screen.getByText('Choose your own password')).toBeInTheDocument()
  })

  it('revokes the token on the server when signing out', async () => {
    sessionStorage.setItem('medai.token', 'test-token')
    const fetchMock = patientApi((url, init) =>
      url.endsWith('/api/auth/logout') && init?.method === 'POST' ? { body: { detail: 'Signed out.' } } : undefined)
    renderApp('/patient')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Sign out' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([u, i]) => String(u).endsWith('/api/auth/logout') && i?.method === 'POST')).toBe(true)
    expect(sessionStorage.getItem('medai.token')).toBeNull()
  })
})

describe('clinician review form', () => {
  it('requires an explicit choice about agreement with the AI output', async () => {
    const { render } = await import('@testing-library/react')
    const { ReviewForm } = await import('../components/ReviewForm')
    const fetchMock = mockApi(() => undefined)
    const analysis = {
      id: 3, upload_id: 9, status: 'completed' as const, model_name: 'm', model_version: 'v', weights_sha256: null,
      score_type: 'op_norm_sigmoid', score_description: '', findings: [], preprocessing: {}, error_message: null,
      duration_ms: 1, created_at: '2026-10-01T10:05:00Z',
    }
    render(<ReviewForm xrayId={9} analysis={analysis} onSaved={() => {}} />)
    const user = userEvent.setup()
    expect(screen.getByLabelText('Agreement with AI output')).toHaveValue('')
    await user.type(screen.getByLabelText('Findings'), 'Clear lungs')
    await user.type(screen.getByLabelText('Impression'), 'Normal study')
    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(screen.getByText('Record whether you agree with the AI output.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
