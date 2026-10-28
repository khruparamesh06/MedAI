import { useState } from 'react'
import { Button, Dialog, TextArea } from './ui'

export interface Decision {
  title: string
  description: string
  confirmLabel: string
  danger?: boolean
  requireNote?: boolean
  run: (note: string) => Promise<void>
}

function DecisionBody({ decision, onClose }: { decision: Decision; onClose: () => void }) {
  const [note, setNote] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const confirm = async () => {
    if (decision.requireNote && !note.trim()) {
      setError('Please give a reason. It will be shown to the requester.')
      return
    }
    setBusy(true)
    try {
      await decision.run(note.trim())
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed.')
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <p>{decision.description}</p>
      <TextArea label={decision.requireNote ? 'Reason (required)' : 'Note (optional)'} rows={3} maxLength={1000}
        value={note} onChange={(e) => setNote(e.target.value)} error={error ?? undefined} />
      <div className="dialog-footer">
        <Button variant="secondary" onClick={onClose}>Back</Button>
        <Button variant={decision.danger ? 'danger' : 'primary'} loading={busy} onClick={confirm}>{decision.confirmLabel}</Button>
      </div>
    </div>
  )
}

/** Confirmation dialog with an optional/required note, used for approve/reject actions. */
export function DecisionDialog({ decision, onClose }: { decision: Decision | null; onClose: () => void }) {
  return (
    <Dialog open={decision !== null} title={decision?.title ?? ''} onClose={onClose}>
      {/* Keyed so each new decision starts with an empty note. */}
      {decision && <DecisionBody key={decision.title + decision.description} decision={decision} onClose={onClose} />}
    </Dialog>
  )
}
