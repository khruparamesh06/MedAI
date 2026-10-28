import { FileText, Printer } from 'lucide-react'
import { api } from '../../api/endpoints'
import { Button, Card, EmptyState, ErrorState, LoadingState, MedicalDisclaimer, PageHeader, StatusBadge } from '../../components/ui'
import { XrayTable } from '../../components/XrayTable'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatDateTime, titleCase } from '../../utils/format'

export function MedicalRecord() {
  const { data, error, loading, reload } = useApi(() => api.myRecord())
  if (loading) return <LoadingState label="Loading your record…" />
  if (error) return <ErrorState error={error} onRetry={reload} />
  if (!data) return null
  const p = data.patient

  return (
    <div className="printable">
      <PageHeader title="Medical record" subtitle="Your uploads, clinician reports, shared notes and appointments."
        actions={<Button variant="secondary" icon={<Printer size={16} />} onClick={() => window.print()}>Print / save as PDF</Button>} />
      <Card title="Patient details">
        <dl className="meta-grid">
          <div><dt>Name</dt><dd>{p.full_name}</dd></div>
          <div><dt>Date of birth</dt><dd>{formatDate(p.date_of_birth)}</dd></div>
          <div><dt>Sex</dt><dd>{p.sex ? titleCase(p.sex) : '—'}</dd></div>
          <div><dt>Email</dt><dd>{p.email}</dd></div>
        </dl>
      </Card>
      <Card title="Imaging">
        {data.xrays.length ? <XrayTable xrays={data.xrays} linkBase="/patient/xrays" /> : <EmptyState icon={<FileText size={22} />} title="No imaging on record" />}
      </Card>
      <Card title="Notes shared by your doctors">
        {data.notes.length ? (
          <ul className="list">
            {data.notes.map((n) => (
              <li key={n.id} className="note"><p>{n.body}</p><span className="small muted">{n.doctor.full_name} · {formatDateTime(n.created_at)}</span></li>
            ))}
          </ul>
        ) : <p className="muted">No notes have been shared with you.</p>}
      </Card>
      <Card title="Appointments">
        {data.appointments.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th scope="col">Date</th><th scope="col">Doctor</th><th scope="col">Reason</th><th scope="col">Status</th></tr></thead>
              <tbody>
                {data.appointments.map((a) => (
                  <tr key={a.id}><td>{formatDateTime(a.scheduled_at)}</td><td>{a.doctor.full_name}</td><td>{a.reason}</td><td><StatusBadge status={a.status} /></td></tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <p className="muted">No appointments on record.</p>}
      </Card>
      <MedicalDisclaimer compact />
    </div>
  )
}
