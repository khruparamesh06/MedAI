import { Search, Users } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../../api/endpoints'
import type { Role, User } from '../../api/types'
import { DecisionDialog, type Decision } from '../../components/DecisionDialog'
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, Pager, StatusBadge } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { formatDate, titleCase } from '../../utils/format'

const LIMIT = 25

export function AdminUsers() {
  const { user: me } = useAuth()
  const toast = useToast()
  const [role, setRole] = useState<Role | ''>('')
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [offset, setOffset] = useState(0)
  const [decision, setDecision] = useState<Decision | null>(null)

  useEffect(() => {
    const t = window.setTimeout(() => { setDebounced(q); setOffset(0) }, 300)
    return () => window.clearTimeout(t)
  }, [q])
  const list = useApi(() => api.adminUsers({ role: role || undefined, q: debounced, limit: LIMIT, offset }), [role, debounced, offset])

  const toggle = (u: User) => {
    const disable = u.status === 'active'
    setDecision({
      title: disable ? `Disable ${u.full_name}?` : `Re-enable ${u.full_name}?`,
      description: disable ? 'The user is signed out immediately and cannot sign in until re-enabled. Their records are kept.' : 'The user will be able to sign in again.',
      confirmLabel: disable ? 'Disable account' : 'Enable account', danger: disable,
      run: async () => {
        await api.adminSetUserStatus(u.id, disable ? 'disabled' : 'active')
        toast('success', disable ? 'Account disabled.' : 'Account enabled.')
        list.reload()
      },
    })
  }

  return (
    <>
      <PageHeader title="Accounts" subtitle="Manage account status for patients, doctors and administrators." />
      <Card>
        <div className="toolbar">
          <label className="search">
            <Search size={16} aria-hidden />
            <span className="sr-only">Search accounts</span>
            <input type="search" placeholder="Search name or email" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <label className="inline-select">
            <span className="sr-only">Filter by role</span>
            <select value={role} onChange={(e) => { setRole(e.target.value as Role | ''); setOffset(0) }}>
              <option value="">All roles</option>
              <option value="patient">Patients</option>
              <option value="doctor">Doctors</option>
              <option value="admin">Administrators</option>
            </select>
          </label>
        </div>
        {list.loading && !list.data ? <LoadingState /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.data?.items.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">Name</th><th scope="col">Role</th><th scope="col">Joined</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {list.data.items.map((u) => (
                    <tr key={u.id}>
                      <td>{u.full_name}<span className="muted small block">{u.email}</span></td>
                      <td>{titleCase(u.role)}</td>
                      <td>{formatDate(u.created_at)}</td>
                      <td><StatusBadge status={u.status} /></td>
                      <td className="cell-action">{u.id !== me?.id && (
                        <Button variant="secondary" onClick={() => toggle(u)}>{u.status === 'active' ? 'Disable' : 'Enable'}</Button>
                      )}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager total={list.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        ) : <EmptyState icon={<Users size={22} />} title="No accounts found" />}
      </Card>
      <DecisionDialog decision={decision} onClose={() => setDecision(null)} />
    </>
  )
}
