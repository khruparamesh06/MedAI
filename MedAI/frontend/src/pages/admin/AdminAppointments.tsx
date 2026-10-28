import { CalendarClock } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/endpoints'
import type { Appointment, AppointmentStatus } from '../../api/types'
import { DecisionDialog, type Decision } from '../../components/DecisionDialog'
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, Pager, StatusBadge } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { formatDateTime } from '../../utils/format'

const LIMIT = 25
const FILTERS: (AppointmentStatus | 'all')[] = ['all', 'requested', 'confirmed', 'completed', 'cancelled', 'declined']

export function AdminAppointments() {
  const toast = useToast()
  const [filter, setFilter] = useState<AppointmentStatus | 'all'>('all')
  const [offset, setOffset] = useState(0)
  const [decision, setDecision] = useState<Decision | null>(null)
  const health = useApi(() => api.health())
  const tz = health.data?.clinic_timezone
  const list = useApi(() => api.appointments({ status: filter === 'all' ? undefined : filter, limit: LIMIT, offset }), [filter, offset])

  const cancel = (a: Appointment) => setDecision({
    title: 'Cancel appointment?',
    description: `${a.patient.full_name} with ${a.doctor.full_name} on ${formatDateTime(a.scheduled_at, tz)}. Both will see the cancellation when they sign in; no message is sent.`,
    confirmLabel: 'Cancel appointment', danger: true,
    run: async () => {
      await api.updateAppointment(a.id, 'cancelled')
      toast('success', 'Appointment cancelled.')
      list.reload()
    },
  })

  return (
    <>
      <PageHeader title="Appointments" subtitle={`All appointments across the hospital${tz ? ` (${tz})` : ''}.`} />
      <Card>
        <div className="tabs" role="tablist" aria-label="Appointment status">
          {FILTERS.map((f) => <button key={f} role="tab" aria-selected={filter === f} className={`tab ${filter === f ? 'active' : ''}`} onClick={() => { setFilter(f); setOffset(0) }}>{f === 'all' ? 'All' : f[0].toUpperCase() + f.slice(1)}</button>)}
        </div>
        {list.loading && !list.data ? <LoadingState /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.data?.items.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">When</th><th scope="col">Patient</th><th scope="col">Doctor</th><th scope="col">Reason</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {list.data.items.map((a) => (
                    <tr key={a.id}>
                      <td>{formatDateTime(a.scheduled_at, tz)}</td>
                      <td>{a.patient.full_name}</td>
                      <td>{a.doctor.full_name}</td>
                      <td>{a.reason}</td>
                      <td><StatusBadge status={a.status} /></td>
                      <td className="cell-action">{(a.status === 'requested' || a.status === 'confirmed') && <Button variant="secondary" onClick={() => cancel(a)}>Cancel</Button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        ) : <EmptyState icon={<CalendarClock size={22} />} title="No appointments" />}
      </Card>
      <DecisionDialog decision={decision} onClose={() => setDecision(null)} />
    </>
  )
}
