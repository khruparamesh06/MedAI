import { CalendarClock, HeartPulse, Lock, ScanLine, Stethoscope } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { api } from '../../api/endpoints'
import { Button, MedicalDisclaimer, Notice, TextInput } from '../../components/ui'
import { useAuth } from '../../hooks/useAuth'
import { homePathFor } from '../../utils/validation'

type ServerState = 'checking' | 'online' | 'offline'

export function Landing() {
  const { user, login, sessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [server, setServer] = useState<ServerState>('checking')

  useEffect(() => {
    document.title = 'MedAI · Sign in'
    api.health().then(() => setServer('online')).catch(() => setServer('offline'))
  }, [])

  if (user) return <Navigate to={homePathFor(user.role)} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!email.trim() || !password) {
      setError('Enter your email and password.')
      return
    }
    setBusy(true)
    try {
      const u = await login(email.trim(), password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/' ? from : homePathFor(u.role), { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="landing">
      <header className="landing-header">
        <span className="brand"><HeartPulse size={24} aria-hidden /> MedAI</span>
        <Link to="/register" className="btn btn-secondary">Create patient account</Link>
      </header>

      <main className="landing-main">
        <section className="landing-intro">
          <p className="eyebrow">Hospital portal · Chest X-ray decision support</p>
          <h1>Imaging, care teams and appointments in one secure place.</h1>
          <p className="lead">
            Patients upload chest X-rays and connect with approved doctors. Clinicians review images
            alongside AI-generated finding scores, and every result stays private to the patient and their care team.
          </p>
          <ul className="feature-list">
            <li><ScanLine size={20} aria-hidden /><div><strong>AI-assisted analysis</strong><span>Scores from a documented, pretrained model, shown with their limitations.</span></div></li>
            <li><Stethoscope size={20} aria-hidden /><div><strong>Clinician review</strong><span>Assigned doctors record their own independent assessment.</span></div></li>
            <li><CalendarClock size={20} aria-hidden /><div><strong>Appointments</strong><span>Request visits within your doctor's published availability.</span></div></li>
            <li><Lock size={20} aria-hidden /><div><strong>Private by design</strong><span>Images are never public; access is checked on every request.</span></div></li>
          </ul>
        </section>

        <section className="card auth-card" aria-labelledby="signin-title">
          <h2 id="signin-title">Sign in</h2>
          {server === 'offline' && (
            <Notice tone="danger" title="Server unreachable">
              The MedAI API is not responding. Start the backend (see README) and refresh this page.
            </Notice>
          )}
          {sessionExpired && <Notice tone="info">Your session ended. Please sign in again.</Notice>}
          <form onSubmit={submit} noValidate className="stack">
            <TextInput label="Email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <TextInput label="Password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            {error && <p className="form-error" role="alert">{error}</p>}
            <Button type="submit" loading={busy} className="btn-block">Sign in</Button>
          </form>
          <p className="small muted">
            New patient? <Link to="/register">Create an account</Link>. Doctor accounts are created by the hospital administrator.
          </p>
        </section>
      </main>

      <footer className="landing-footer">
        <MedicalDisclaimer compact />
      </footer>
    </div>
  )
}
