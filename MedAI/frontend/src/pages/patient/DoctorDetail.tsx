import { ArrowLeft, CalendarClock, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { Button, Card, ErrorState, LoadingState, Notice, PageHeader, StatusBadge, TextArea } from '../../components/ui'
import { errorMessage, useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { WEEKDAYS, formatDate, shortTime } from '../../utils/format'

export function DoctorDetail() {
  const doctorId = Number(useParams().id)
  const toast = useToast()
  const doctor = useApi(() => api.doctor(doctorId), [doctorId])
  const assignments = useApi(() => api.myAssignments())
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  if (doctor.loading) return <LoadingState />
  if (doctor.error) return <ErrorState error={doctor.error} onRetry={doctor.reload} />
  if (!doctor.data) return null
  const d = doctor.data
  const mine = assignments.data?.filter((a) => a.doctor.id === d.user_id) ?? []
  const active = mine.find((a) => a.status === 'approved' || a.status === 'pending')
  const lastRejected = mine.find((a) => a.status === 'rejected')

  const request = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.requestAssignment(d.user_id, reason.trim())
      toast('success', 'Request sent. An administrator will review it.')
      setReason('')
      assignments.reload()
    } catch (err) {
      toast('error', errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const withdraw = async () => {
    if (!active) return
    setCancelling(true)
    try {
      await api.cancelAssignment(active.id)
      toast('success', 'Request withdrawn.')
      assignments.reload()
    } catch (err) {
      toast('error', errorMessage(err))
    } finally {
      setCancelling(false)
    }
  }

  const byDay = WEEKDAYS.map((name, i) => ({ name, slots: d.availability.filter((s) => s.weekday === i) })).filter((x) => x.slots.length)

  return (
    <>
      <Link to="/patient/doctors" className="back-link"><ArrowLeft size={16} aria-hidden /> All doctors</Link>
      <PageHeader title={d.full_name} subtitle={`${d.specialty} · ${d.years_experience} years of experience`} />
      <div className="grid-2-1">
        <div className="stack">
          <Card title="About">
            <p>{d.bio || <span className="muted">No biography provided.</span>}</p>
            {d.clinic_location && <p className="muted">Location: {d.clinic_location}</p>}
          </Card>
          <Card title="Weekly availability">
            {byDay.length ? (
              <table className="table compact">
                <tbody>
                  {byDay.map((day) => (
                    <tr key={day.name}><th scope="row">{day.name}</th><td>{day.slots.map((s) => `${shortTime(s.start_time)}–${shortTime(s.end_time)}`).join(', ')}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted">This doctor has not published availability yet.</p>}
          </Card>
        </div>
        <Card title="Care assignment">
          {assignments.loading ? <LoadingState /> : active?.status === 'approved' ? (
            <div className="stack">
              <StatusBadge status="approved" label="Assigned to you" />
              <p className="muted">This doctor can view your X-rays and add clinical reviews.</p>
              <Link to={`/patient/appointments?doctor=${d.user_id}`} className="btn btn-primary"><CalendarClock size={16} aria-hidden /> Book an appointment</Link>
            </div>
          ) : active?.status === 'pending' ? (
            <div className="stack">
              <StatusBadge status="pending" label="Request pending" />
              <p className="muted">Requested {formatDate(active.created_at)}. An administrator will approve or reject the request.</p>
              <Button variant="secondary" loading={cancelling} onClick={withdraw}>Withdraw request</Button>
            </div>
          ) : (
            <form onSubmit={request} className="stack">
              {lastRejected && (
                <Notice tone="warning" title="Previous request was not approved">
                  {lastRejected.decision_note || 'No reason was given.'} You may submit a new request.
                </Notice>
              )}
              <p className="muted">Request this doctor as part of your care team. Once approved, they can access your X-rays and records.</p>
              <TextArea label="Reason for request (optional)" rows={3} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
              <Button type="submit" loading={busy} icon={<UserPlus size={16} />}>Request this doctor</Button>
            </form>
          )}
        </Card>
      </div>
    </>
  )
}
