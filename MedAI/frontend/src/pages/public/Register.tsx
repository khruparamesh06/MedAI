import { HeartPulse } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { Button, SelectInput, TextInput } from '../../components/ui'
import { useAuth } from '../../hooks/useAuth'
import { isoDate } from '../../utils/format'
import { homePathFor, validateRegistration, type RegisterForm } from '../../utils/validation'

export function Register() {
  const { user, register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState<RegisterForm>({ full_name: '', email: '', password: '', confirm: '', date_of_birth: '', sex: '', phone: '' })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [today] = useState(() => isoDate(new Date()))

  useEffect(() => { document.title = 'MedAI · Create account' }, [])
  if (user) return <Navigate to={homePathFor(user.role)} replace />

  const set = (key: keyof RegisterForm) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setFormError(null)
    const v = validateRegistration(form)
    setErrors(v)
    if (Object.keys(v).length) return
    setBusy(true)
    try {
      await register({
        full_name: form.full_name.trim(), email: form.email.trim(), password: form.password,
        date_of_birth: form.date_of_birth || null, sex: form.sex || null, phone: form.phone.trim() || null,
      })
      navigate('/patient', { replace: true })
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors)
        setFormError(err.message)
      } else setFormError('Registration failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <Link to="/" className="brand"><HeartPulse size={24} aria-hidden /> MedAI</Link>
      <section className="card auth-card wide" aria-labelledby="register-title">
        <h1 id="register-title">Create a patient account</h1>
        <p className="muted">Doctor and administrator accounts cannot be created here.</p>
        <form onSubmit={submit} noValidate className="form-grid">
          <TextInput label="Full name" autoComplete="name" value={form.full_name} onChange={set('full_name')} error={errors.full_name} required />
          <TextInput label="Email" type="email" autoComplete="email" value={form.email} onChange={set('email')} error={errors.email} required />
          <TextInput label="Password" type="password" autoComplete="new-password" value={form.password} onChange={set('password')} error={errors.password}
            hint="At least 10 characters, mixing letters with numbers or symbols." required />
          <TextInput label="Confirm password" type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} error={errors.confirm} required />
          <TextInput label="Date of birth (optional)" type="date" max={today} value={form.date_of_birth} onChange={set('date_of_birth')} error={errors.date_of_birth} />
          <SelectInput label="Sex (optional)" value={form.sex} onChange={set('sex')} error={errors.sex}>
            <option value="">Prefer not to answer</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
            <option value="prefer_not_to_say">Prefer not to say</option>
          </SelectInput>
          <TextInput label="Phone (optional)" type="tel" autoComplete="tel" value={form.phone} onChange={set('phone')} error={errors.phone} />
          <div className="form-span">
            {formError && <p className="form-error" role="alert">{formError}</p>}
            <Button type="submit" loading={busy}>Create account</Button>
            <p className="small muted">Already registered? <Link to="/">Sign in</Link></p>
          </div>
        </form>
      </section>
    </div>
  )
}
