import { useState, type FormEvent } from 'react'
import { ApiError } from '../api/client'
import { api, type ReviewInput } from '../api/endpoints'
import type { Analysis, Review, ReviewAgreement } from '../api/types'
import { errorMessage } from '../hooks/useApi'
import { useToast } from '../hooks/useToast'
import { Button, SelectInput, TextArea } from './ui'

export function ReviewForm({ xrayId, analysis, draft, onSaved }: {
  xrayId: number; analysis: Analysis | null; draft?: Review; onSaved: () => void
}) {
  const toast = useToast()
  const completed = analysis?.status === 'completed' ? analysis : null
  const [form, setForm] = useState({
    findings: draft?.findings ?? '',
    impression: draft?.impression ?? '',
    recommendation: draft?.recommendation ?? '',
    // No pre-selected agreement for a completed analysis: the clinician must choose explicitly.
    ai_agreement: (draft?.ai_agreement ?? (completed ? '' : 'not_applicable')) as ReviewAgreement | '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState<'draft' | 'final' | null>(null)

  const save = async (status: 'draft' | 'final') => {
    const v: Record<string, string> = {}
    if (form.findings.trim().length < 3) v.findings = 'Describe your findings.'
    if (form.impression.trim().length < 3) v.impression = 'Add an impression.'
    if (!form.ai_agreement) v.ai_agreement = 'Record whether you agree with the AI output.'
    setErrors(v)
    if (Object.keys(v).length) return
    if (status === 'final' && !window.confirm('Finalise this review? Final reviews become visible to the patient and cannot be edited.')) return
    setBusy(status)
    const input: ReviewInput = { ...form, ai_agreement: form.ai_agreement as ReviewAgreement, status, analysis_id: completed?.id ?? null }
    try {
      if (draft) await api.updateReview(draft.id, input)
      else await api.createReview(xrayId, input)
      toast('success', status === 'final' ? 'Review finalised and shared with the patient.' : 'Draft saved.')
      onSaved()
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors)
      toast('error', errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void save('final')
  }

  return (
    <form className="stack" onSubmit={onSubmit} noValidate>
      <TextArea label="Findings" value={form.findings} onChange={(e) => setForm({ ...form, findings: e.target.value })} error={errors.findings} maxLength={5000}
        hint="Your independent read of the image." />
      <TextArea label="Impression" rows={3} value={form.impression} onChange={(e) => setForm({ ...form, impression: e.target.value })} error={errors.impression} maxLength={2000} />
      <TextArea label="Recommendation (optional)" rows={2} value={form.recommendation} onChange={(e) => setForm({ ...form, recommendation: e.target.value })} maxLength={2000} />
      <SelectInput label="Agreement with AI output" value={form.ai_agreement} onChange={(e) => setForm({ ...form, ai_agreement: e.target.value as ReviewAgreement })}
        error={errors.ai_agreement}
        hint={completed ? `Refers to analysis #${completed.id}. Form your own read before comparing.` : 'No completed AI analysis is available for this image.'}>
        {completed && <option value="">Select…</option>}
        {completed && <option value="agree">Agree</option>}
        {completed && <option value="partially_agree">Partially agree</option>}
        {completed && <option value="disagree">Disagree</option>}
        <option value="not_applicable">Not applicable</option>
      </SelectInput>
      <div className="row">
        <Button type="button" variant="secondary" loading={busy === 'draft'} disabled={busy !== null} onClick={() => void save('draft')}>Save draft</Button>
        <Button type="submit" loading={busy === 'final'} disabled={busy !== null}>Finalise review</Button>
      </div>
    </form>
  )
}
