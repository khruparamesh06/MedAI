import { Upload } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, Pager } from '../../components/ui'
import { XrayTable } from '../../components/XrayTable'
import { useApi } from '../../hooks/useApi'

const LIMIT = 15

export function XrayHistory() {
  const [offset, setOffset] = useState(0)
  const { data, error, loading, reload } = useApi(() => api.myXrays(LIMIT, offset), [offset])
  return (
    <>
      <PageHeader title="X-ray history" subtitle="All images you have uploaded, with AI analysis and clinician review status."
        actions={<Link to="/patient/xrays/new" className="btn btn-primary"><Upload size={16} aria-hidden /> Upload X-ray</Link>} />
      <Card>
        {loading ? <LoadingState /> : error ? <ErrorState error={error} onRetry={reload} /> : data && data.items.length ? (
          <>
            <XrayTable xrays={data.items} linkBase="/patient/xrays" />
            <Pager total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </>
        ) : (
          <EmptyState icon={<Upload size={22} />} title="You have not uploaded any X-rays">
            <Link to="/patient/xrays/new" className="btn btn-secondary">Upload an X-ray</Link>
          </EmptyState>
        )}
      </Card>
    </>
  )
}
