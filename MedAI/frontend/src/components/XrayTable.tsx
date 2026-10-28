import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { Xray } from '../api/types'
import { formatBytes, formatDateTime } from '../utils/format'
import { analysisLabel } from '../utils/validation'
import { StatusBadge } from './ui'

export function XrayTable({ xrays, linkBase }: { xrays: Xray[]; linkBase: string }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Uploaded</th>
            <th scope="col">File</th>
            <th scope="col">View</th>
            <th scope="col">AI analysis</th>
            <th scope="col">Clinician review</th>
            <th scope="col"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {xrays.map((x) => {
            const a = analysisLabel(x)
            return (
              <tr key={x.id}>
                <td>{formatDateTime(x.created_at)}</td>
                <td><span className="truncate" title={x.original_filename}>{x.original_filename}</span><span className="muted small block">{x.width}×{x.height} · {formatBytes(x.size_bytes)}</span></td>
                <td>{x.view_position ?? '—'}</td>
                <td><StatusBadge status={a.status} label={a.label} /></td>
                <td>{x.review_count > 0 ? <StatusBadge status="final" label={`${x.review_count} final`} /> : <StatusBadge status="draft" label="Awaiting" />}</td>
                <td className="cell-action"><Link to={`${linkBase}/${x.id}`} className="btn btn-ghost" aria-label={`Open X-ray uploaded ${formatDateTime(x.created_at)}`}>Open <ChevronRight size={16} aria-hidden /></Link></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
