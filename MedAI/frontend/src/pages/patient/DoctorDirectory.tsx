import { ChevronRight, Search, Stethoscope } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/endpoints'
import type { AssignmentStatus } from '../../api/types'
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, Pager, StatusBadge } from '../../components/ui'
import { useApi } from '../../hooks/useApi'

const LIMIT = 12

export function DoctorDirectory() {
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [specialty, setSpecialty] = useState('')
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    const t = window.setTimeout(() => { setDebounced(query); setOffset(0) }, 300)
    return () => window.clearTimeout(t)
  }, [query])

  const doctors = useApi(() => api.doctors({ q: debounced, specialty, limit: LIMIT, offset }), [debounced, specialty, offset])
  const specialties = useApi(() => api.specialties())
  const assignments = useApi(() => api.myAssignments())

  const statusFor = (doctorId: number): AssignmentStatus | undefined =>
    assignments.data?.find((a) => a.doctor.id === doctorId && (a.status === 'approved' || a.status === 'pending'))?.status

  return (
    <>
      <PageHeader title="Find a doctor" subtitle="Only doctors approved by the hospital administrator are listed." />
      <Card>
        <div className="toolbar">
          <label className="search">
            <Search size={16} aria-hidden />
            <span className="sr-only">Search doctors</span>
            <input type="search" placeholder="Search by name or specialty" value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>
          <label className="inline-select">
            <span className="sr-only">Filter by specialty</span>
            <select value={specialty} onChange={(e) => { setSpecialty(e.target.value); setOffset(0) }}>
              <option value="">All specialties</option>
              {specialties.data?.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </label>
        </div>
        {doctors.loading && !doctors.data ? <LoadingState /> : doctors.error ? <ErrorState error={doctors.error} onRetry={doctors.reload} /> :
          doctors.data && doctors.data.items.length ? (
            <>
              <ul className="doctor-grid">
                {doctors.data.items.map((d) => {
                  const st = statusFor(d.user_id)
                  return (
                    <li key={d.user_id}>
                      <Link to={`/patient/doctors/${d.user_id}`} className="doctor-card">
                        <div className="avatar" aria-hidden>{d.full_name.replace(/^Dr\.?\s*/, '').charAt(0)}</div>
                        <div className="doctor-card-body">
                          <strong>{d.full_name}</strong>
                          <span className="muted">{d.specialty} · {d.years_experience} yrs</span>
                          {d.clinic_location && <span className="small muted">{d.clinic_location}</span>}
                          {st && <StatusBadge status={st} label={st === 'approved' ? 'Your doctor' : 'Request pending'} />}
                        </div>
                        <ChevronRight size={18} aria-hidden className="muted" />
                      </Link>
                    </li>
                  )
                })}
              </ul>
              <Pager total={doctors.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
            </>
          ) : <EmptyState icon={<Stethoscope size={22} />} title="No doctors match your search" />}
      </Card>
    </>
  )
}
