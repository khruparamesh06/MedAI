import { ArrowLeft, NotebookPen } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge, TextArea } from '../../components/ui'
import { XrayTable } from '../../components/XrayTable'
import { errorMessage, useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { formatDate, formatDateTime, titleCase } from '../../utils/format'

export function DoctorPatientReview() {
  const patientId = Number(useParams().id)
  const toast = useToast()
  const record = useApi(() => api.patientRecord(patientId), [patientId])
  const [body, setBody] = useState('')
  const [shared, setShared] = useState(false)
  const [busy, setBusy] = useState(false)

  if (record.loading && !record.data) return <LoadingState label="Loading patient record…" />
  if (record.error) return <ErrorState error={record.error} onRetry={record.reload} />
  if (!record.data) return null
  const { patient, xrays, notes, appointments } = record.data

  const addNote = async (e: FormEvent) => {
    e.preventDefault()
    if (!body.trim()) return
    setBusy(true)
    try {
      await api.addNote(patient.id, body.trim(), shared)
      setBody('')
      setShared(false)
      toast('success', 'Note added.')
      record.reload()
    } catch (err) {
      toast('error', errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Link to="/doctor/patients" className="back-link"><ArrowLeft size={16} aria-hidden /> My patients</Link>
      <PageHeader title={patient.full_name} subtitle={`DOB ${formatDate(patient.date_of_birth)} · ${patient.sex ? titleCase(patient.sex) : 'Sex not specified'} · ${patient.phone ?? 'No phone on file'}`} />
      <Card title="Imaging">
        {xrays.length ? <XrayTable xrays={xrays} linkBase="/doctor/xrays" /> : <EmptyState title="This patient has not uploaded any X-rays" />}
      </Card>
      <div className="grid-2">
        <Card title="Clinical notes">
          <form onSubmit={addNote} className="stack">
            <TextArea label="New note" rows={3} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />
            <label className="checkbox"><input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} /> Share this note with the patient</label>
            <div><Button type="submit" loading={busy} disabled={!body.trim()} icon={<NotebookPen size={16} />}>Add note</Button></div>
          </form>
          <ul className="list">
            {notes.map((n) => (
              <li key={n.id} className="note">
                <p>{n.body}</p>
                <span className="small muted">{n.doctor.full_name} · {formatDateTime(n.created_at)} · {n.visible_to_patient ? 'Shared with patient' : 'Care team only'}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Appointments with you">
          {appointments.length ? (
            <ul className="list">
              {appointments.map((a) => (
                <li key={a.id} className="list-row"><span>{formatDateTime(a.scheduled_at)}<span className="muted small block">{a.reason}</span></span><StatusBadge status={a.status} /></li>
              ))}
            </ul>
          ) : <p className="muted">No appointments.</p>}
          <Link to="/doctor/appointments" className="btn btn-ghost">Manage appointments</Link>
        </Card>
      </div>
    </>
  )
}
