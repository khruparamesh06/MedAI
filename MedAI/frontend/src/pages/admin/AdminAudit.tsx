import { ScrollText } from 'lucide-react'
import { useState } from 'react'
import { api } from '../../api/endpoints'
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, Pager } from '../../components/ui'
import { useApi } from '../../hooks/useApi'
import { formatDateTime } from '../../utils/format'

const LIMIT = 50

export function AdminAudit() {
  const [offset, setOffset] = useState(0)
  const { data, error, loading, reload } = useApi(() => api.adminAudit(LIMIT, offset), [offset])
  return (
    <>
      <PageHeader title="Activity log" subtitle="Security-relevant actions recorded by the server. Entries cannot be edited." />
      <Card>
        {loading && !data ? <LoadingState /> : error ? <ErrorState error={error} onRetry={reload} /> : data?.items.length ? (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th scope="col">Time</th><th scope="col">Action</th><th scope="col">Entity</th><th scope="col">Actor</th><th scope="col">Detail</th></tr></thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <td>{formatDateTime(e.created_at)}</td>
                      <td><code>{e.action}</code></td>
                      <td>{e.entity_type} #{e.entity_id ?? '—'}</td>
                      <td>{e.actor_id ? `User #${e.actor_id}` : 'System'}</td>
                      <td className="small muted">{Object.keys(e.detail).length ? Object.entries(e.detail).map(([k, v]) => `${k}: ${String(v)}`).join(', ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        ) : <EmptyState icon={<ScrollText size={22} />} title="No activity recorded yet" />}
      </Card>
    </>
  )
}
