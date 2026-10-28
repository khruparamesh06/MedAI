import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import type { Sex } from '../api/types'
import { Button, Card, Notice, PageHeader, SelectInput, TextInput } from '../components/ui'
import { errorMessage } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { formatDate, isoDate } from '../utils/format'

export function AccountPage() {
  const { user, setUser, acceptToken, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [profile, setProfile] = useState({
    full_name: user?.full_name ?? '', date_of_birth: user?.date_of_birth ?? '', sex: (user?.sex ?? '') as Sex | '', phone: user?.phone ?? '',
  })
  const [profileErrors, setProfileErrors] = useState<Record<string, string>>({})
  const [savingProfile, setSavingProfile] = useState(false)
  const [pw, setPw] = useState({ current: '', next: '', confirm: '' })
  const [pwError, setPwError] = useState<string | null>(null)
  const [savingPw, setSavingPw] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const [today] = useState(() => isoDate(new Date()))

  if (!user) return null
  const isPatient = user.role === 'patient'

  const saveProfile = async (e: FormEvent) => {
    e.preventDefault()
    if (profile.full_name.trim().length < 2) {
      setProfileErrors({ full_name: 'Enter your full name.' })
      return
    }
    setProfileErrors({})
    setSavingProfile(true)
    try {
      const updated = await api.updateMe(isPatient
        ? { full_name: profile.full_name.trim(), date_of_birth: profile.date_of_birth || null, sex: profile.sex || null, phone: profile.phone.trim() || null }
        : { full_name: profile.full_name.trim() })
      setUser(updated)
      toast('success', 'Profile saved.')
    } catch (err) {
      if (err instanceof ApiError) setProfileErrors(err.fieldErrors)
      toast('error', errorMessage(err))
    } finally {
      setSavingProfile(false)
    }
  }

  const changePassword = async (e: FormEvent) => {
    e.preventDefault()
    setPwError(null)
    if (pw.next.length < 10) return setPwError('New password must be at least 10 characters.')
    if (pw.next !== pw.confirm) return setPwError('New passwords do not match.')
    if (pw.next === pw.current) return setPwError('The new password must be different from the current one.')
    setSavingPw(true)
    try {
      acceptToken(await api.changePassword(pw.current, pw.next))
      setPw({ current: '', next: '', confirm: '' })
      toast('success', 'Password changed. Other sessions have been signed out.')
    } catch (err) {
      setPwError(errorMessage(err))
    } finally {
      setSavingPw(false)
    }
  }

  const signOutEverywhere = async () => {
    setSigningOut(true)
    try {
      await api.logoutAll()
      logout()
      navigate('/', { replace: true })
    } catch (err) {
      toast('error', errorMessage(err))
      setSigningOut(false)
    }
  }

  return (
    <>
      <PageHeader title="Account settings" subtitle={`${user.email} · member since ${formatDate(user.created_at)}`} />
      {user.must_change_password && (
        <Notice tone="warning" title="Choose your own password">
          Your account was created with a temporary password. Change it below to continue using MedAI.
        </Notice>
      )}
      <div className="grid-2">
        <Card title="Personal details">
          <form onSubmit={saveProfile} className="stack" noValidate>
            <TextInput label="Full name" value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })} error={profileErrors.full_name} />
            {isPatient && (
              <>
                <TextInput label="Date of birth" type="date" max={today} value={profile.date_of_birth}
                  onChange={(e) => setProfile({ ...profile, date_of_birth: e.target.value })} error={profileErrors.date_of_birth} />
                <SelectInput label="Sex" value={profile.sex} onChange={(e) => setProfile({ ...profile, sex: e.target.value as Sex | '' })}>
                  <option value="">Not specified</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                  <option value="prefer_not_to_say">Prefer not to say</option>
                </SelectInput>
                <TextInput label="Phone" type="tel" value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })} error={profileErrors.phone} />
              </>
            )}
            <p className="small muted">Email address and role can only be changed by an administrator.</p>
            <div><Button type="submit" loading={savingProfile}>Save details</Button></div>
          </form>
        </Card>
        <div className="stack">
          <Card title="Change password">
            <form onSubmit={changePassword} className="stack" noValidate>
              <TextInput label="Current password" type="password" autoComplete="current-password" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />
              <TextInput label="New password" type="password" autoComplete="new-password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })}
                hint="At least 10 characters, mixing letters with numbers or symbols." />
              <TextInput label="Confirm new password" type="password" autoComplete="new-password" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
              {pwError && <p className="form-error" role="alert">{pwError}</p>}
              <div><Button type="submit" loading={savingPw} disabled={!pw.current || !pw.next}>Change password</Button></div>
            </form>
          </Card>
          <Card title="Sessions">
            <p className="muted">Sign out of MedAI on every device and browser where you are signed in.</p>
            <Button variant="secondary" loading={signingOut} onClick={signOutEverywhere}>Sign out everywhere</Button>
          </Card>
        </div>
      </div>
    </>
  )
}
