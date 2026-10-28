import { Plus, Trash2 } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { api } from '../../api/endpoints'
import type { AvailabilitySlot, DoctorProfile } from '../../api/types'
import { Button, Card, ErrorState, LoadingState, Notice, PageHeader, StatusBadge, TextArea, TextInput } from '../../components/ui'
import { errorMessage, useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { WEEKDAYS, formatDateTime, shortTime } from '../../utils/format'
import { validateSlots } from '../../utils/validation'

type Slot = { weekday: number; start_time: string; end_time: string }

function ProfileForm({ profile, onSaved }: { profile: DoctorProfile; onSaved: (p: DoctorProfile) => void }) {
  const toast = useToast()
  const [form, setForm] = useState({
    specialty: profile.specialty, license_number: profile.license_number, years_experience: String(profile.years_experience),
    bio: profile.bio, clinic_location: profile.clinic_location,
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  const save = async (e: FormEvent) => {
    e.preventDefault()
    const v: Record<string, string> = {}
    if (form.specialty.trim().length < 2) v.specialty = 'Enter your specialty.'
    if (form.license_number.trim().length < 3) v.license_number = 'Enter your registration / license number.'
    const years = Number(form.years_experience)
    if (!Number.isInteger(years) || years < 0 || years > 80) v.years_experience = 'Enter a whole number between 0 and 80.'
    setErrors(v)
    if (Object.keys(v).length) return
    if (profile.status === 'approved' && (form.specialty !== profile.specialty || form.license_number !== profile.license_number)
      && !window.confirm('Changing your specialty or license number requires re-approval, and you will lose access to patient data until then. Continue?')) return
    setBusy(true)
    try {
      const updated = await api.updateMyDoctorProfile({ ...form, years_experience: years })
      toast('success', 'Profile saved.')
      onSaved(updated)
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors)
      toast('error', errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} className="stack" noValidate>
      <div className="form-grid">
        <TextInput label="Specialty" value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} error={errors.specialty} />
        <TextInput label="License / registration number" value={form.license_number} onChange={(e) => setForm({ ...form, license_number: e.target.value })} error={errors.license_number}
          hint="Visible only to administrators." />
        <TextInput label="Years of experience" type="number" min={0} max={80} value={form.years_experience} onChange={(e) => setForm({ ...form, years_experience: e.target.value })} error={errors.years_experience} />
        <TextInput label="Clinic location" value={form.clinic_location} onChange={(e) => setForm({ ...form, clinic_location: e.target.value })} />
      </div>
      <TextArea label="Short biography" maxLength={2000} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} />
      <div><Button type="submit" loading={busy}>Save profile</Button></div>
    </form>
  )
}

function AvailabilityEditor({ initial, onSaved }: { initial: AvailabilitySlot[]; onSaved: (p: DoctorProfile) => void }) {
  const toast = useToast()
  const [slots, setSlots] = useState<Slot[]>(initial.map((s) => ({ ...s, start_time: shortTime(s.start_time), end_time: shortTime(s.end_time) })))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const update = (i: number, patch: Partial<Slot>) => setSlots((all) => all.map((s, j) => (j === i ? { ...s, ...patch } : s)))

  const save = async () => {
    const err = validateSlots(slots)
    setError(err)
    if (err) return
    setBusy(true)
    try {
      onSaved(await api.updateMyAvailability(slots))
      toast('success', 'Availability saved.')
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      {slots.length === 0 && <p className="muted">No availability yet. Patients can only book appointments within these hours.</p>}
      {slots.map((s, i) => (
        <div key={i} className="slot-row">
          <label><span className="sr-only">Day</span>
            <select value={s.weekday} onChange={(e) => update(i, { weekday: Number(e.target.value) })}>
              {WEEKDAYS.map((d, n) => <option key={d} value={n}>{d}</option>)}
            </select>
          </label>
          <label><span className="sr-only">Start time</span><input type="time" step={900} value={s.start_time} onChange={(e) => update(i, { start_time: e.target.value })} /></label>
          <span aria-hidden>–</span>
          <label><span className="sr-only">End time</span><input type="time" step={900} value={s.end_time} onChange={(e) => update(i, { end_time: e.target.value })} /></label>
          <button type="button" className="icon-button" aria-label={`Remove ${WEEKDAYS[s.weekday]} slot`} onClick={() => setSlots((all) => all.filter((_, j) => j !== i))}><Trash2 size={16} /></button>
        </div>
      ))}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="row">
        <Button variant="secondary" icon={<Plus size={16} />} onClick={() => setSlots((all) => [...all, { weekday: 0, start_time: '09:00', end_time: '12:00' }])}>Add time range</Button>
        <Button loading={busy} onClick={save}>Save availability</Button>
      </div>
    </div>
  )
}

export function DoctorProfilePage() {
  const toast = useToast()
  const { data, error, loading, reload, setData } = useApi(() => api.myDoctorProfile())
  const health = useApi(() => api.health())
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { document.title = 'Profile · MedAI' }, [])
  if (loading && !data) return <LoadingState />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null

  const submit = async () => {
    setSubmitting(true)
    try {
      setData(await api.submitMyDoctorProfile())
      toast('success', 'Profile submitted for administrator approval.')
    } catch (err) {
      toast('error', errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader title="Profile & availability" subtitle={<>Approval status: <StatusBadge status={data.status} /></>}
        actions={(data.status === 'draft' || data.status === 'rejected') && <Button loading={submitting} onClick={submit}>Submit for approval</Button>} />
      {data.status === 'rejected' && <Notice tone="danger" title="Profile not approved">{data.review_note ?? 'No reason given.'} Update your details and submit again.</Notice>}
      {data.status === 'pending' && <Notice tone="info">Submitted {formatDateTime(data.submitted_at)}. An administrator will review your profile.</Notice>}
      {data.status === 'draft' && <Notice tone="warning">Your profile has not been submitted yet. Save your details, then choose “Submit for approval”.</Notice>}
      <div className="grid-2">
        <Card title="Professional details"><ProfileForm key={data.id + data.status} profile={data} onSaved={setData} /></Card>
        <Card title={`Weekly availability (${health.data?.clinic_timezone ?? 'clinic time'})`}>
          <AvailabilityEditor initial={data.availability} onSaved={setData} />
        </Card>
      </div>
    </>
  )
}
