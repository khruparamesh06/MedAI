import { CalendarClock, ClipboardCheck, ClipboardList, Cpu, ScanLine, Stethoscope, UserCheck, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { ModelStatusCard } from '../../components/ModelStatusCard'
import { Card, ErrorState, LoadingState, PageHeader, Stat } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { formatDateTime, titleCase } from '../../utils/format'

export function AdminDashboard() {
  const stats = useApi(() => api.adminStats())
  const model = useApi(() => api.modelStatus())
  const audit = useApi(() => api.adminAudit(8, 0))
  const s = stats.data

  return (
    <>
      <PageHeader title="Administration" subtitle="Approvals, accounts and system activity." />
      {stats.loading ? <LoadingState /> : stats.error ? <ErrorState error={stats.error} onRetry={stats.reload} /> : s && (
        <>
          <h2 className="section-title">Needs attention</h2>
          <div className="stats">
            <Stat label="Doctor profiles awaiting approval" value={s.doctors_pending} icon={<UserCheck size={18} />} to="/admin/doctors" />
            <Stat label="Assignment requests pending" value={s.assignments_pending} icon={<ClipboardCheck size={18} />} to="/admin/assignments" />
          </div>
          <h2 className="section-title">System</h2>
          <div className="stats">
            <Stat label="Patients" value={s.patients} icon={<Users size={18} />} to="/admin/users" />
            <Stat label="Approved doctors" value={s.doctors_approved} icon={<Stethoscope size={18} />} />
            <Stat label="Upcoming appointments" value={s.appointments_upcoming} icon={<CalendarClock size={18} />} to="/admin/appointments" />
            <Stat label="X-rays uploaded" value={s.xrays_total} icon={<ClipboardList size={18} />} />
            <Stat label="AI analyses run" value={s.analyses_total} icon={<ScanLine size={18} />} />
            <Stat label="AI model" value={s.model_available ? 'Ready' : 'Not configured'} icon={<Cpu size={18} />} />
          </div>
        </>
      )}
      <ModelStatusCard status={model.data} />
      <Card title="Recent activity" actions={<Link to="/admin/audit" className="btn btn-ghost">Full log</Link>}>
        {audit.loading ? <LoadingState /> : audit.error ? <ErrorState error={audit.error} onRetry={audit.reload} /> : (
          <ul className="list">
            {audit.data?.items.map((e) => (
              <li key={e.id} className="list-row"><span>{titleCase(e.action.replace('.', ' · '))}<span className="muted small block">{e.entity_type} #{e.entity_id ?? '—'} · actor #{e.actor_id ?? 'system'}</span></span><span className="small muted">{formatDateTime(e.created_at)}</span></li>
            ))}
            {!audit.data?.items.length && <li className="muted">No activity yet.</li>}
          </ul>
        )}
      </Card>
    </>
  )
}
