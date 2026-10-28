import { CalendarClock, ChevronRight, ClipboardList, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../../api/endpoints'
import type { DoctorProfile } from '../../api/types'
import { ModelStatusCard } from '../../components/ModelStatusCard'
import { Card, EmptyState, ErrorState, LoadingState, Notice, PageHeader, Stat, StatusBadge } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { formatDateTime } from '../../utils/format'
import { analysisLabel } from '../../utils/validation'

export function ProfileGate({ profile }: { profile: DoctorProfile }) {
  if (profile.status === 'approved') return null
  const messages: Record<string, string> = {
    draft: 'Complete your professional profile and submit it for administrator approval. Patient data is available only after approval.',
    pending: 'Your profile has been submitted and is awaiting administrator approval. Patient data will become available once it is approved.',
    rejected: `Your profile was not approved${profile.review_note ? `: “${profile.review_note}”` : '.'} Update it and resubmit.`,
  }
  return (
    <Notice tone={profile.status === 'rejected' ? 'danger' : 'warning'} title={`Profile status: ${profile.status}`}>
      <p>{messages[profile.status]}</p>
      <Link to="/doctor/profile" className="btn btn-secondary">Go to profile</Link>
    </Notice>
  )
}

function ApprovedDashboard() {
  const patients = useApi(() => api.assignedPatients())
  const queue = useApi(() => api.reviewQueue())
  const appts = useApi(() => api.appointments({ upcoming: true, limit: 5 }))
  const model = useApi(() => api.modelStatus())
  return (
    <>
      <div className="stats">
        <Stat label="Assigned patients" value={patients.data?.length ?? '—'} icon={<Users size={18} />} to="/doctor/patients" />
        <Stat label="X-rays awaiting review" value={queue.data?.length ?? '—'} icon={<ClipboardList size={18} />} />
        <Stat label="Upcoming appointments" value={appts.data?.total ?? '—'} icon={<CalendarClock size={18} />} to="/doctor/appointments" />
      </div>
      <ModelStatusCard status={model.data} />
      <div className="grid-2-1">
        <Card title="Review queue">
          {queue.loading ? <LoadingState /> : queue.error ? <ErrorState error={queue.error} onRetry={queue.reload} /> : queue.data?.length ? (
            <ul className="list">
              {queue.data.map((x) => {
                const a = analysisLabel(x)
                return (
                  <li key={x.id}>
                    <Link to={`/doctor/xrays/${x.id}`} className="list-row list-link">
                      <span>{patients.data?.find((p) => p.patient.id === x.owner_id)?.patient.full_name ?? `Patient #${x.owner_id}`}
                        <span className="muted small block">Uploaded {formatDateTime(x.created_at)}</span></span>
                      <span className="row-tight"><StatusBadge status={a.status} label={a.label} /><ChevronRight size={16} aria-hidden /></span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          ) : <EmptyState title="Nothing waiting for review" />}
        </Card>
        <Card title="Upcoming appointments" actions={<Link to="/doctor/appointments" className="btn btn-ghost">Manage</Link>}>
          {appts.loading ? <LoadingState /> : appts.error ? <ErrorState error={appts.error} onRetry={appts.reload} /> : appts.data?.items.length ? (
            <ul className="list">
              {appts.data.items.map((a) => (
                <li key={a.id} className="list-row"><span>{formatDateTime(a.scheduled_at)}<span className="muted small block">{a.patient.full_name}</span></span><StatusBadge status={a.status} /></li>
              ))}
            </ul>
          ) : <p className="muted">No upcoming appointments.</p>}
        </Card>
      </div>
    </>
  )
}

export function DoctorDashboard() {
  const { user } = useAuth()
  const profile = useApi(() => api.myDoctorProfile())
  return (
    <>
      <PageHeader title={`Welcome, ${user?.full_name ?? ''}`} subtitle="Your patients, review queue and schedule." />
      {profile.loading ? <LoadingState /> : profile.error ? <ErrorState error={profile.error} onRetry={profile.reload} /> :
        profile.data && (profile.data.status === 'approved' ? <ApprovedDashboard /> : <ProfileGate profile={profile.data} />)}
    </>
  )
}
