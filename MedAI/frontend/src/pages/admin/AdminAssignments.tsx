import { ClipboardCheck } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/endpoints'
import type { Assignment, AssignmentStatus } from '../../api/types'
import { DecisionDialog, type Decision } from '../../components/DecisionDialog'
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, Pager, StatusBadge } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { formatDateTime } from '../../utils/format'

const TABS: (AssignmentStatus | 'all')[] = ['pending', 'approved', 'rejected', 'cancelled', 'ended', 'all']
const LIMIT = 25

export function AdminAssignments() {
  const toast = useToast()
  const [tab, setTab] = useState<AssignmentStatus | 'all'>('pending')
  const [offset, setOffset] = useState(0)
  const [decision, setDecision] = useState<Decision | null>(null)
  const list = useApi(() => api.adminAssignments(tab === 'all' ? undefined : tab, LIMIT, offset), [tab, offset])

  const open = (a: Assignment, action: 'approve' | 'reject' | 'end') => setDecision({
    title: action === 'approve' ? 'Approve assignment?' : action === 'reject' ? 'Reject assignment request?' : 'End assignment?',
    description: action === 'approve'
      ? `${a.doctor.full_name} will be able to view ${a.patient.full_name}'s X-rays and records.`
      : action === 'reject' ? `${a.patient.full_name} will see that the request was not approved.`
        : `${a.doctor.full_name} will immediately lose access to ${a.patient.full_name}'s records.`,
    confirmLabel: action === 'approve' ? 'Approve' : action === 'reject' ? 'Reject' : 'End assignment',
    danger: action !== 'approve', requireNote: action === 'reject',
    run: async (note) => {
      await api.adminDecideAssignment(a.id, action, note || undefined)
      toast('success', `Assignment ${action === 'end' ? 'ended' : action + 'd'}.`)
      list.reload()
    },
  })

  return (
    <>
      <PageHeader title="Assignment requests" subtitle="Approving a request gives the doctor access to that patient's records." />
      <Card>
        <div className="tabs" role="tablist" aria-label="Request status">
          {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => { setTab(t); setOffset(0) }}>{t === 'all' ? 'All' : t[0].toUpperCase() + t.slice(1)}</button>)}
        </div>
        {list.loading && !list.data ? <LoadingState /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.data?.items.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">Patient</th><th scope="col">Doctor</th><th scope="col">Reason</th><th scope="col">Requested</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {list.data.items.map((a) => (
                    <tr key={a.id}>
                      <td>{a.patient.full_name}<span className="muted small block">{a.patient.email}</span></td>
                      <td>{a.doctor.full_name}</td>
                      <td>{a.request_reason || <span className="muted">—</span>}{a.decision_note && <span className="muted small block">Note: {a.decision_note}</span>}</td>
                      <td>{formatDateTime(a.created_at)}</td>
                      <td><StatusBadge status={a.status} /></td>
                      <td className="cell-action">
                        <div className="row-tight">
                          {a.status === 'pending' && <>
                            <Button variant="secondary" onClick={() => open(a, 'reject')}>Reject</Button>
                            <Button onClick={() => open(a, 'approve')}>Approve</Button>
                          </>}
                          {a.status === 'approved' && <Button variant="secondary" onClick={() => open(a, 'end')}>End</Button>}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        ) : <EmptyState icon={<ClipboardCheck size={22} />} title={tab === 'pending' ? 'No pending requests' : 'Nothing in this list'} />}
      </Card>
      <DecisionDialog decision={decision} onClose={() => setDecision(null)} />
    </>
  )
}
