import { UserCheck, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { api } from '../../api/endpoints'
import type { DoctorProfileStatus } from '../../api/types'
import { DecisionDialog, type Decision } from '../../components/DecisionDialog'
import { Button, Card, Dialog, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, TextInput } from '../../components/ui'
import { errorMessage, useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { WEEKDAYS, formatDateTime, shortTime } from '../../utils/format'

const TABS: (DoctorProfileStatus | 'all')[] = ['pending', 'approved', 'rejected', 'draft', 'all']

function CreateDoctorDialog({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const toast = useToast()
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (form.full_name.trim().length < 2 || !form.email.includes('@') || form.password.length < 10) {
      setError('Enter a name, a valid email, and a temporary password of at least 10 characters.')
      return
    }
    setBusy(true)
    try {
      await api.adminCreateDoctor(form.email.trim(), form.full_name.trim(), form.password)
      toast('success', 'Doctor account created. Share the temporary password with the doctor securely.')
      setForm({ full_name: '', email: '', password: '' })
      onCreated()
      onClose()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} title="Create doctor account" onClose={onClose}>
      <form onSubmit={submit} className="stack" noValidate>
        <p className="muted small">The doctor signs in with this temporary password, completes their profile and submits it for approval. MedAI does not send emails.</p>
        <TextInput label="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        <TextInput label="Email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <TextInput label="Temporary password" type="password" autoComplete="new-password" value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })} hint="At least 10 characters with letters and numbers. Ask the doctor to change it after first sign-in." />
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-footer">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={busy}>Create account</Button>
        </div>
      </form>
    </Dialog>
  )
}

export function AdminDoctors() {
  const toast = useToast()
  const [tab, setTab] = useState<DoctorProfileStatus | 'all'>('pending')
  const [creating, setCreating] = useState(false)
  const [decision, setDecision] = useState<Decision | null>(null)
  const list = useApi(() => api.adminDoctors(tab === 'all' ? undefined : tab), [tab])

  const decide = (profileId: number, name: string, approve: boolean) => setDecision({
    title: approve ? `Approve ${name}?` : `Reject ${name}?`,
    description: approve
      ? 'The doctor will appear in the patient directory and can be assigned patients.'
      : 'The doctor will be asked to correct their profile and resubmit.',
    confirmLabel: approve ? 'Approve' : 'Reject', danger: !approve, requireNote: !approve,
    run: async (note) => {
      await api.adminDecideDoctor(profileId, approve, note || undefined)
      toast('success', approve ? 'Doctor approved.' : 'Doctor profile rejected.')
      list.reload()
    },
  })

  return (
    <>
      <PageHeader title="Doctor approvals" subtitle="Verify credentials before a doctor can access patient data."
        actions={<Button icon={<UserPlus size={16} />} onClick={() => setCreating(true)}>Create doctor account</Button>} />
      <Card>
        <div className="tabs" role="tablist" aria-label="Profile status">
          {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>{t === 'all' ? 'All' : t[0].toUpperCase() + t.slice(1)}</button>)}
        </div>
        {list.loading && !list.data ? <LoadingState /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.data?.length ? (
          <ul className="review-list">
            {list.data.map(({ user, profile }) => (
              <li key={profile.id} className="review-item">
                <div className="row-between">
                  <div>
                    <strong>{user.full_name}</strong> <StatusBadge status={profile.status} />
                    <span className="muted small block">{user.email} · account {user.status}</span>
                  </div>
                  {profile.status === 'pending' && (
                    <div className="row-tight">
                      <Button variant="secondary" onClick={() => decide(profile.id, user.full_name, false)}>Reject</Button>
                      <Button icon={<UserCheck size={16} />} onClick={() => decide(profile.id, user.full_name, true)}>Approve</Button>
                    </div>
                  )}
                </div>
                <dl className="meta-grid">
                  <div><dt>Specialty</dt><dd>{profile.specialty || '—'}</dd></div>
                  <div><dt>License no.</dt><dd>{profile.license_number || '—'}</dd></div>
                  <div><dt>Experience</dt><dd>{profile.years_experience} years</dd></div>
                  <div><dt>Submitted</dt><dd>{formatDateTime(profile.submitted_at)}</dd></div>
                  <div><dt>Location</dt><dd>{profile.clinic_location || '—'}</dd></div>
                  <div><dt>Availability</dt><dd>{profile.availability.length ? profile.availability.map((s) => `${WEEKDAYS[s.weekday].slice(0, 3)} ${shortTime(s.start_time)}–${shortTime(s.end_time)}`).join(', ') : '—'}</dd></div>
                </dl>
                {profile.bio && <p className="small">{profile.bio}</p>}
                {profile.review_note && <p className="small muted">Review note: {profile.review_note}</p>}
              </li>
            ))}
          </ul>
        ) : <EmptyState icon={<UserCheck size={22} />} title={tab === 'pending' ? 'No profiles awaiting approval' : 'No doctors in this list'} />}
      </Card>
      <CreateDoctorDialog open={creating} onClose={() => setCreating(false)} onCreated={() => { setTab('draft'); list.reload() }} />
      <DecisionDialog decision={decision} onClose={() => setDecision(null)} />
    </>
  )
}
