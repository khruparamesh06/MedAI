import { CalendarClock, Plus } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { api } from '../api/endpoints'
import type { Appointment, AppointmentStatus } from '../api/types'
import {
  Button, Card, Dialog, EmptyState, ErrorState, LoadingState, Notice, PageHeader, Pager, SelectInput, StatusBadge, TextArea, TextInput,
} from '../components/ui'
import { errorMessage, useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { backendWeekday, formatDateTime, isoDate, startTimesWithin } from '../utils/format'

const LIMIT = 20
type Action = Exclude<AppointmentStatus, 'requested'>

function BookingForm({ clinicTz, initialDoctor, onBooked }: { clinicTz: string; initialDoctor: number | null; onBooked: () => void }) {
  const toast = useToast()
  const assignments = useApi(() => api.myAssignments())
  const myDoctors = useMemo(() => assignments.data?.filter((a) => a.status === 'approved').map((a) => a.doctor) ?? [], [assignments.data])
  const [doctorId, setDoctorId] = useState<number | null>(initialDoctor)
  const effectiveDoctor = doctorId ?? myDoctors[0]?.id ?? null
  const doctor = useApi(() => (effectiveDoctor ? api.doctor(effectiveDoctor) : Promise.resolve(null)), [effectiveDoctor])
  const [date, setDate] = useState('')
  const [time, setTime] = useState('')
  const [duration, setDuration] = useState(30)
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  const [[minDate, maxDate]] = useState(() => {
    const day = (offset: number) => { const d = new Date(); d.setDate(d.getDate() + offset); return isoDate(d) }
    return [day(1), day(180)]
  })

  const availability = doctor.data?.availability ?? []
  const options = date && availability.length
    ? startTimesWithin(availability.filter((s) => s.weekday === backendWeekday(date)), duration) : []

  if (assignments.loading) return <LoadingState />
  if (!myDoctors.length) {
    return <Notice title="No assigned doctor">You can book appointments once an administrator approves a doctor assignment. Visit “Find a doctor” to send a request.</Notice>
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const v: Record<string, string> = {}
    if (!date) v.date = 'Choose a date.'
    if (!time) v.time = 'Choose a start time.'
    if (reason.trim().length < 3) v.reason = 'Briefly describe the reason for the visit.'
    setErrors(v)
    if (Object.keys(v).length || !effectiveDoctor) return
    setBusy(true)
    try {
      await api.requestAppointment({ doctor_id: effectiveDoctor, date, start_time: time, reason: reason.trim(), duration_minutes: duration })
      toast('success', 'Appointment requested. The doctor will confirm it.')
      onBooked()
    } catch (err) {
      toast('error', errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form id="booking-form" className="stack" onSubmit={submit} noValidate>
      <SelectInput label="Doctor" value={effectiveDoctor ?? ''} onChange={(e) => { setDoctorId(Number(e.target.value)); setTime('') }}>
        {myDoctors.map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}
      </SelectInput>
      <div className="form-grid">
        <TextInput label="Date" type="date" min={minDate} max={maxDate} value={date}
          onChange={(e) => { setDate(e.target.value); setTime('') }} error={errors.date} />
        <SelectInput label="Length" value={duration} onChange={(e) => { setDuration(Number(e.target.value)); setTime('') }}>
          <option value={15}>15 minutes</option>
          <option value={30}>30 minutes</option>
          <option value={45}>45 minutes</option>
          <option value={60}>60 minutes</option>
        </SelectInput>
      </div>
      {availability.length ? (
        <SelectInput label={`Start time (${clinicTz})`} value={time} onChange={(e) => setTime(e.target.value)} error={errors.time} disabled={!date}
          hint={date && !options.length ? 'The doctor has no availability on this day. Try another date.' : undefined}>
          <option value="">{date ? 'Select a time' : 'Choose a date first'}</option>
          {options.map((t) => <option key={t} value={t}>{t}</option>)}
        </SelectInput>
      ) : (
        <TextInput label={`Start time (${clinicTz})`} type="time" step={900} value={time} onChange={(e) => setTime(e.target.value)} error={errors.time}
          hint="This doctor has not published availability; choose a time on a 15-minute boundary." />
      )}
      <TextArea label="Reason for visit" rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} error={errors.reason} />
      <div><Button type="submit" loading={busy}>Request appointment</Button></div>
    </form>
  )
}

export function AppointmentsPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [params] = useSearchParams()
  const preselectedDoctor = params.get('doctor') ? Number(params.get('doctor')) : null
  const [view, setView] = useState<'upcoming' | 'all'>('upcoming')
  const [offset, setOffset] = useState(0)
  const [booking, setBooking] = useState(preselectedDoctor !== null)
  const [pending, setPending] = useState<{ appt: Appointment; action: Action } | null>(null)
  const [note, setNote] = useState('')
  const [acting, setActing] = useState(false)
  const health = useApi(() => api.health())
  const list = useApi(() => api.appointments({ upcoming: view === 'upcoming', limit: LIMIT, offset }), [view, offset])
  const clinicTz = health.data?.clinic_timezone ?? 'UTC'
  const isPatient = user?.role === 'patient'

  const [now] = useState(() => Date.now())
  const actionsFor = (a: Appointment): Action[] => {
    const future = new Date(a.scheduled_at).getTime() > now
    if (isPatient) return (a.status === 'requested' || a.status === 'confirmed') && future ? ['cancelled'] : []
    if (a.status === 'requested') return ['confirmed', 'declined']
    if (a.status === 'confirmed') return future ? ['cancelled'] : ['completed', 'cancelled']
    return []
  }

  const LABEL: Record<Action, string> = { confirmed: 'Confirm', declined: 'Decline', cancelled: 'Cancel', completed: 'Mark completed' }

  const act = async () => {
    if (!pending) return
    setActing(true)
    try {
      await api.updateAppointment(pending.appt.id, pending.action, isPatient ? undefined : note.trim() || undefined)
      toast('success', `Appointment ${pending.action}.`)
      setPending(null)
      setNote('')
      list.reload()
    } catch (err) {
      toast('error', errorMessage(err))
    } finally {
      setActing(false)
    }
  }

  return (
    <>
      <PageHeader title="Appointments" subtitle={`Times are shown in the clinic time zone (${clinicTz}).`}
        actions={isPatient && <Button icon={<Plus size={16} />} onClick={() => setBooking(true)}>New appointment</Button>} />
      {isPatient && booking && (
        <Card title="Request an appointment" actions={<Button variant="ghost" onClick={() => setBooking(false)}>Close</Button>}>
          <BookingForm clinicTz={clinicTz} initialDoctor={preselectedDoctor} onBooked={() => { setBooking(false); setView('upcoming'); list.reload() }} />
        </Card>
      )}
      <Card>
        <div className="tabs" role="tablist" aria-label="Appointment filter">
          {(['upcoming', 'all'] as const).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} className={`tab ${view === v ? 'active' : ''}`} onClick={() => { setView(v); setOffset(0) }}>
              {v === 'upcoming' ? 'Upcoming' : 'All appointments'}
            </button>
          ))}
        </div>
        {list.loading && !list.data ? <LoadingState /> : list.error ? (
          list.error instanceof ApiError && list.error.status === 403 && user?.role === 'doctor'
            ? <EmptyState icon={<CalendarClock size={22} />} title="Profile approval required">
                <p className="muted">{list.error.message}</p>
                <Link to="/doctor/profile" className="btn btn-secondary">Open your profile</Link>
              </EmptyState>
            : <ErrorState error={list.error} onRetry={list.reload} />
        ) : list.data?.items.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">When</th><th scope="col">{isPatient ? 'Doctor' : 'Patient'}</th><th scope="col">Reason</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {list.data.items.map((a) => (
                    <tr key={a.id}>
                      <td>{formatDateTime(a.scheduled_at, clinicTz)}<span className="muted small block">{a.duration_minutes} min</span></td>
                      <td>{isPatient ? a.doctor.full_name : a.patient.full_name}</td>
                      <td>{a.reason}{a.doctor_note && <span className="muted small block">Doctor: {a.doctor_note}</span>}</td>
                      <td><StatusBadge status={a.status} /></td>
                      <td className="cell-action">
                        <div className="row-tight">
                          {actionsFor(a).map((action) => (
                            <Button key={action} variant={action === 'confirmed' || action === 'completed' ? 'primary' : 'secondary'}
                              onClick={() => setPending({ appt: a, action })}>{LABEL[action]}</Button>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        ) : <EmptyState icon={<CalendarClock size={22} />} title={view === 'upcoming' ? 'No upcoming appointments' : 'No appointments yet'} />}
      </Card>

      <Dialog open={pending !== null} title={pending ? `${LABEL[pending.action]} appointment?` : ''} onClose={() => setPending(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setPending(null)}>Back</Button>
          <Button variant={pending?.action === 'cancelled' || pending?.action === 'declined' ? 'danger' : 'primary'} loading={acting} onClick={act}>
            {pending ? LABEL[pending.action] : ''}
          </Button>
        </>}>
        {pending && (
          <div className="stack">
            <p>{formatDateTime(pending.appt.scheduled_at, clinicTz)} with {isPatient ? pending.appt.doctor.full_name : pending.appt.patient.full_name}.</p>
            {!isPatient && <TextArea label="Note to patient (optional)" rows={2} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />}
            <p className="small muted">MedAI does not send emails or SMS. The patient will see the status change when they sign in.</p>
          </div>
        )}
      </Dialog>
    </>
  )
}
