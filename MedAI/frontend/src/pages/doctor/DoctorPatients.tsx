import { ChevronRight, Search, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { api } from '../../api/endpoints'
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { formatDate, formatDateTime } from '../../utils/format'

export function DoctorPatients() {
  const { data, error, loading, reload } = useApi(() => api.assignedPatients())
  const [q, setQ] = useState('')
  const rows = (data ?? []).filter((p) => p.patient.full_name.toLowerCase().includes(q.trim().toLowerCase()))

  return (
    <>
      <PageHeader title="My patients" subtitle="Patients whose assignment to you has been approved by an administrator." />
      <Card>
        <div className="toolbar">
          <label className="search">
            <Search size={16} aria-hidden />
            <span className="sr-only">Filter patients</span>
            <input type="search" placeholder="Filter by name" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
        </div>
        {loading ? <LoadingState /> : error ? (
          error instanceof ApiError && error.status === 403
            ? <EmptyState title="Profile approval required">{error.message} <Link to="/doctor/profile">Open your profile</Link></EmptyState>
            : <ErrorState error={error} onRetry={reload} />
        ) : rows.length ? (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th scope="col">Patient</th><th scope="col">Assigned since</th><th scope="col">X-rays</th><th scope="col">Awaiting review</th><th scope="col">Next appointment</th><th scope="col"><span className="sr-only">Open</span></th></tr></thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.patient.id}>
                    <td>{p.patient.full_name}<span className="muted small block">DOB {formatDate(p.patient.date_of_birth)}</span></td>
                    <td>{formatDate(p.assigned_since)}</td>
                    <td className="num">{p.xray_count}</td>
                    <td>{p.pending_review_count ? <StatusBadge status="pending" label={`${p.pending_review_count} pending`} /> : <span className="muted">None</span>}</td>
                    <td>{formatDateTime(p.next_appointment)}</td>
                    <td className="cell-action"><Link to={`/doctor/patients/${p.patient.id}`} className="btn btn-ghost">Open <ChevronRight size={16} aria-hidden /></Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState icon={<Users size={22} />} title={q ? 'No patients match this filter' : 'No patients are assigned to you yet'} />}
      </Card>
    </>
  )
}
