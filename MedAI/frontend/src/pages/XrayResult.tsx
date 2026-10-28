import { ArrowLeft, ScanLine, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/endpoints'
import type { Review } from '../api/types'
import { AnalysisPanel } from '../components/AnalysisPanel'
import { ProtectedImage } from '../components/ProtectedImage'
import { ReviewForm } from '../components/ReviewForm'
import {
  Button, Card, Dialog, EmptyState, ErrorState, LoadingState, MedicalDisclaimer, Notice, PageHeader, StatusBadge,
} from '../components/ui'
import { errorMessage, useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { useToast } from '../hooks/useToast'
import { formatBytes, formatDateTime, titleCase } from '../utils/format'

function ReviewCard({ review }: { review: Review }) {
  return (
    <article className="review">
      <header className="row-between">
        <div>
          <strong>{review.doctor.full_name}</strong>
          <span className="muted small block">{formatDateTime(review.updated_at)}</span>
        </div>
        <StatusBadge status={review.status} label={review.status === 'final' ? 'Final' : 'Draft (only you can see this)'} />
      </header>
      <dl className="review-body">
        <dt>Findings</dt><dd>{review.findings}</dd>
        <dt>Impression</dt><dd>{review.impression}</dd>
        {review.recommendation && (<><dt>Recommendation</dt><dd>{review.recommendation}</dd></>)}
        <dt>Agreement with AI output</dt><dd>{titleCase(review.ai_agreement)}</dd>
      </dl>
    </article>
  )
}

export function XrayResult() {
  const { id } = useParams()
  const xrayId = Number(id)
  const { user } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const xray = useApi(() => api.xray(xrayId), [xrayId])
  const model = useApi(() => api.modelStatus())
  const [analyzing, setAnalyzing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [editingDraft, setEditingDraft] = useState<Review | null>(null)

  const isDoctor = user?.role === 'doctor'
  const backTo = isDoctor ? (xray.data ? `/doctor/patients/${xray.data.owner_id}` : '/doctor/patients') : '/patient/xrays'

  if (!Number.isInteger(xrayId) || xrayId <= 0) return <ErrorState error={new Error('Invalid X-ray link.')} />
  if (xray.loading && !xray.data) return <LoadingState label="Loading X-ray…" />
  if (xray.error) return <ErrorState error={xray.error} onRetry={xray.reload} />
  if (!xray.data) return null
  const x = xray.data
  const latest = x.analyses[0] ?? null
  const hasFinal = x.reviews.some((r) => r.status === 'final')
  const myDraft = x.reviews.find((r) => r.status === 'draft' && r.doctor.id === user?.id)

  const runAnalysis = async () => {
    setAnalyzing(true)
    try {
      const result = await api.analyze(x.id)
      toast(result.status === 'completed' ? 'success' : 'error',
        result.status === 'completed' ? 'AI analysis complete.' : 'The image could not be analysed.')
      xray.reload()
    } catch (err) {
      toast('error', errorMessage(err))
      model.reload()
    } finally {
      setAnalyzing(false)
    }
  }

  const remove = async () => {
    setDeleting(true)
    try {
      await api.deleteXray(x.id)
      toast('success', 'X-ray deleted.')
      navigate('/patient/xrays', { replace: true })
    } catch (err) {
      toast('error', errorMessage(err))
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const modelReady = model.data?.available === true

  return (
    <>
      <Link to={backTo} className="back-link"><ArrowLeft size={16} aria-hidden /> Back</Link>
      <PageHeader title={`Chest X-ray · ${formatDateTime(x.created_at)}`}
        subtitle={isDoctor ? `Patient: ${x.owner.full_name}` : 'AI analysis and clinician review'}
        actions={!isDoctor && !hasFinal && <Button variant="ghost" icon={<Trash2 size={16} />} onClick={() => setConfirmDelete(true)}>Delete</Button>} />

      <div className="result-layout">
        <div className="stack">
          <ProtectedImage xrayId={x.id} alt={`Chest X-ray uploaded ${formatDateTime(x.created_at)}`} />
          <Card>
            <dl className="meta-grid">
              <div><dt>File</dt><dd className="truncate" title={x.original_filename}>{x.original_filename}</dd></div>
              <div><dt>Dimensions</dt><dd>{x.width}×{x.height}px · {formatBytes(x.size_bytes)}</dd></div>
              <div><dt>View</dt><dd>{x.view_position ?? 'Unknown'}</dd></div>
              <div><dt>Status</dt><dd><StatusBadge status={x.status} /></dd></div>
            </dl>
            {x.patient_note && <p className="note-quote"><span className="muted small block">Patient note</span>{x.patient_note}</p>}
          </Card>
        </div>

        <div className="stack">
          <Card title="AI analysis" actions={latest && modelReady && (
            <Button variant="secondary" loading={analyzing} icon={<ScanLine size={16} />} onClick={runAnalysis}>Re-run</Button>)}>
            {model.loading && !model.data ? <LoadingState label="Checking model…" /> : !latest ? (
              modelReady ? (
                <EmptyState icon={<ScanLine size={22} />} title="Not analysed yet">
                  <p className="muted">Run the {model.data?.model_name} model on this image. Results are decision support only.</p>
                  <Button loading={analyzing} icon={<ScanLine size={16} />} onClick={runAnalysis}>Run AI analysis</Button>
                </EmptyState>
              ) : (
                <Notice tone="warning" title="Model not configured">
                  {model.data?.reason || model.error?.message || 'No genuine AI model is installed on this server.'} No AI
                  result is shown because no inference has taken place. A clinician can still review this image.
                </Notice>
              )
            ) : (
              <>
                {!modelReady && <Notice tone="warning">The model is currently unavailable; showing the most recent stored result.</Notice>}
                <AnalysisPanel analysis={latest} />
                {x.analyses.length > 1 && <p className="small muted">{x.analyses.length - 1} earlier analysis run(s) are kept in the record.</p>}
              </>
            )}
          </Card>

          <Card title="Clinician review">
            {x.reviews.length === 0 && !isDoctor && <p className="muted">No clinician has finalised a review of this image yet.</p>}
            <div className="stack">
              {x.reviews.map((r) => (
                <div key={r.id}>
                  <ReviewCard review={r} />
                  {isDoctor && r.status === 'draft' && r.doctor.id === user?.id && editingDraft?.id !== r.id && (
                    <Button variant="ghost" onClick={() => setEditingDraft(r)}>Edit draft</Button>
                  )}
                </div>
              ))}
            </div>
            {isDoctor && (editingDraft || !myDraft) && (
              <div className="review-form">
                <h3>{editingDraft ? 'Edit draft review' : 'Add your review'}</h3>
                <ReviewForm key={editingDraft?.id ?? 'new'} xrayId={x.id} analysis={latest} draft={editingDraft ?? undefined}
                  onSaved={() => { setEditingDraft(null); xray.reload() }} />
              </div>
            )}
          </Card>
          <MedicalDisclaimer />
        </div>
      </div>

      <Dialog open={confirmDelete} title="Delete this X-ray?" onClose={() => setConfirmDelete(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmDelete(false)}>Cancel</Button>
          <Button variant="danger" loading={deleting} onClick={remove}>Delete permanently</Button>
        </>}>
        <p>The image and its AI analysis results will be permanently removed. This cannot be undone.</p>
      </Dialog>
    </>
  )
}
