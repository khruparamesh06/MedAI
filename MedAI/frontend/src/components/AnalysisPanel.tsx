import { useId } from 'react'
import type { Analysis } from '../api/types'
import { formatDateTime } from '../utils/format'
import { Notice, StatusBadge } from './ui'

function ScoreBar({ score, threshold }: { score: number; threshold: boolean }) {
  return (
    <div className="scorebar" aria-hidden>
      <div className={`scorebar-fill ${threshold ? 'above' : ''}`} style={{ width: `${Math.round(score * 100)}%` }} />
      <div className="scorebar-mark" title="Model operating threshold (0.5)" />
    </div>
  )
}

export function AnalysisPanel({ analysis }: { analysis: Analysis }) {
  const captionId = useId()
  if (analysis.status === 'failed') {
    return (
      <Notice tone="danger" title="Analysis could not be completed">
        <p>{analysis.error_message}</p>
        <p className="small">No scores were produced. {formatDateTime(analysis.created_at)}</p>
      </Notice>
    )
  }
  const opNorm = analysis.score_type === 'op_norm_sigmoid'
  return (
    <div className="stack">
      <dl className="meta-grid">
        <div><dt>Model</dt><dd>{analysis.model_name}</dd></div>
        <div><dt>Version</dt><dd>{analysis.model_version}</dd></div>
        <div><dt>Analysed</dt><dd>{formatDateTime(analysis.created_at)}</dd></div>
        <div><dt>Score type</dt><dd>{opNorm ? 'Uncalibrated, threshold-normalised' : 'Uncalibrated sigmoid'}</dd></div>
      </dl>

      <Notice tone="info" title="How to read these scores">
        <p>{analysis.score_description}</p>
        <p>The model gives scores for any grayscale image, even one that is not a chest X-ray, and has not been
          validated on this hospital's patients. Research / decision-support output only; a clinician must interpret it.</p>
      </Notice>

      <div className="table-wrap">
        <table className="table findings" aria-describedby={captionId}>
          <caption id={captionId} className="sr-only">Model scores for each supported finding, highest first</caption>
          <thead>
            <tr><th scope="col">Finding</th><th scope="col">Score</th><th scope="col" className="bar-col">Relative to threshold</th>{opNorm && <th scope="col">Model flag</th>}</tr>
          </thead>
          <tbody>
            {analysis.findings.map((f) => (
              <tr key={f.label}>
                <td>{f.display_name}</td>
                <td className="num">{f.score.toFixed(2)}</td>
                <td className="bar-col"><ScoreBar score={f.score} threshold={!!f.above_operating_threshold} /></td>
                {opNorm && <td>{f.above_operating_threshold ? <StatusBadge status="pending" label="Above threshold" /> : <span className="muted small">Below</span>}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Notice tone="warning" title="Severity">
        MedAI does not estimate disease severity. A higher score does not mean a more severe condition;
        severity requires clinical assessment.
      </Notice>
      <details className="small muted">
        <summary>Technical details</summary>
        <p>Preprocessing: {Object.entries(analysis.preprocessing).map(([k, v]) => `${k}=${String(v)}`).join(', ')}</p>
        <p>Weights SHA-256: <code className="break">{analysis.weights_sha256 ?? 'n/a'}</code></p>
        {analysis.duration_ms !== null && <p>Inference time: {analysis.duration_ms} ms</p>}
      </details>
    </div>
  )
}
