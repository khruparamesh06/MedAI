import { CalendarClock, ClipboardList, Stethoscope, Upload } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { ModelStatusCard } from '../../components/ModelStatusCard'
import { EmptyState, ErrorState, LoadingState, MedicalDisclaimer, PageHeader, Card, Stat, StatusBadge } from '../../components/ui'
import { XrayTable } from '../../components/XrayTable'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { formatDateTime } from '../../utils/format'

export function PatientDashboard() {
  const { user } = useAuth()
  const xrays = useApi(() => api.myXrays(5, 0))
  const appts = useApi(() => api.appointments({ upcoming: true, limit: 3 }))
  const assignments = useApi(() => api.myAssignments())
  const model = useApi(() => api.modelStatus())

  const careTeam = assignments.data?.filter((a) => a.status === 'approved') ?? []
  const pendingRequests = assignments.data?.filter((a) => a.status === 'pending') ?? []

  return (
    <>
      <PageHeader title={`Hello, ${user?.full_name.split(' ')[0] ?? ''}`} subtitle="Your imaging, care team and appointments at a glance."
        actions={<Link to="/patient/xrays/new" className="btn btn-primary"><Upload size={16} aria-hidden /> Upload X-ray</Link>} />

      <div className="stats">
        <Stat label="X-rays uploaded" value={xrays.data?.total ?? '—'} icon={<ClipboardList size={18} />} to="/patient/xrays" />
        <Stat label="Upcoming appointments" value={appts.data?.total ?? '—'} icon={<CalendarClock size={18} />} to="/patient/appointments" />
        <Stat label="Doctors in your care team" value={assignments.data ? careTeam.length : '—'} icon={<Stethoscope size={18} />} to="/patient/doctors" />
      </div>

      <ModelStatusCard status={model.data} />

      <div className="grid-2-1">
        <Card title="Recent X-rays" actions={<Link to="/patient/xrays" className="btn btn-ghost">View all</Link>}>
          {xrays.loading ? <LoadingState /> : xrays.error ? <ErrorState error={xrays.error} onRetry={xrays.reload} /> :
            xrays.data && xrays.data.items.length ? <XrayTable xrays={xrays.data.items} linkBase="/patient/xrays" /> :
              <EmptyState icon={<Upload size={22} />} title="No X-rays yet">
                <Link to="/patient/xrays/new" className="btn btn-secondary">Upload your first X-ray</Link>
              </EmptyState>}
        </Card>

        <div className="stack">
          <Card title="Care team">
            {assignments.loading ? <LoadingState /> : assignments.error ? <ErrorState error={assignments.error} onRetry={assignments.reload} /> : (
              <ul className="list">
                {careTeam.map((a) => (
                  <li key={a.id} className="list-row"><span>{a.doctor.full_name}</span><StatusBadge status="approved" label="Assigned" /></li>
                ))}
                {pendingRequests.map((a) => (
                  <li key={a.id} className="list-row"><span>{a.doctor.full_name}</span><StatusBadge status="pending" label="Awaiting approval" /></li>
                ))}
                {!careTeam.length && !pendingRequests.length && (
                  <li><EmptyState title="No doctor assigned"><Link to="/patient/doctors" className="btn btn-secondary">Find a doctor</Link></EmptyState></li>
                )}
              </ul>
            )}
          </Card>
          <Card title="Next appointments" actions={<Link to="/patient/appointments" className="btn btn-ghost">Manage</Link>}>
            {appts.loading ? <LoadingState /> : appts.error ? <ErrorState error={appts.error} onRetry={appts.reload} /> :
              appts.data?.items.length ? (
                <ul className="list">
                  {appts.data.items.map((a) => (
                    <li key={a.id} className="list-row"><span>{formatDateTime(a.scheduled_at)}<span className="muted small block">{a.doctor.full_name}</span></span><StatusBadge status={a.status} /></li>
                  ))}
                </ul>
              ) : <p className="muted">No upcoming appointments.</p>}
          </Card>
        </div>
      </div>
      <MedicalDisclaimer />
    </>
  )
}
