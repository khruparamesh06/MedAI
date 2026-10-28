import { Cpu } from 'lucide-react'
import type { ModelStatus } from '../api/types'
import { StatusBadge } from './ui'

export function ModelStatusCard({ status }: { status: ModelStatus | null }) {
  if (!status) return null
  return (
    <div className="model-status">
      <Cpu size={20} aria-hidden />
      <div>
        <div className="row-tight">
          <strong>AI model</strong>
          <StatusBadge status={status.state} label={status.available ? 'Available' : status.state === 'error' ? 'Error' : 'Model not configured'} />
        </div>
        <p className="small muted">
          {status.available
            ? `${status.model_name} (${status.model_version}) · ${status.labels.length} supported findings`
            : status.reason || 'No genuine model weights are installed. Uploads and all other features still work.'}
        </p>
      </div>
    </div>
  )
}
