import { CircleAlert, Info, LoaderCircle, RefreshCw, TriangleAlert, WifiOff } from 'lucide-react'
import {
  useEffect, useId, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode,
  type SelectHTMLAttributes, type TextareaHTMLAttributes,
} from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { titleCase } from '../utils/format'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

export function Button({ variant = 'primary', loading = false, icon, children, className = '', disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; icon?: ReactNode }) {
  return (
    <button className={`btn btn-${variant} ${className}`} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <LoaderCircle size={16} className="spin" aria-hidden /> : icon}
      {children && <span>{children}</span>}
    </button>
  )
}

interface FieldProps { label: string; error?: string; hint?: string; children: (id: string, describedBy?: string) => ReactNode }

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  return (
    <div className={`field ${error ? 'field-invalid' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children(id, describedBy)}
      {hint && !error && <p id={`${id}-hint`} className="field-hint">{hint}</p>}
      {error && <p id={`${id}-error`} className="field-error">{error}</p>}
    </div>
  )
}

export function TextInput({ label, error, hint, ...rest }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; hint?: string }) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(id, describedBy) => <input id={id} aria-invalid={!!error || undefined} aria-describedby={describedBy} {...rest} />}
    </Field>
  )
}

export function SelectInput({ label, error, hint, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; error?: string; hint?: string }) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(id, describedBy) => <select id={id} aria-invalid={!!error || undefined} aria-describedby={describedBy} {...rest}>{children}</select>}
    </Field>
  )
}

export function TextArea({ label, error, hint, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string; error?: string; hint?: string }) {
  return (
    <Field label={label} error={error} hint={hint}>
      {(id, describedBy) => <textarea id={id} aria-invalid={!!error || undefined} aria-describedby={describedBy} rows={4} {...rest} />}
    </Field>
  )
}

export function Card({ title, actions, children, className = '' }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card-header">
          {title && <h2 className="card-title">{title}</h2>}
          {actions && <div className="card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  useEffect(() => { document.title = `${title} · MedAI` }, [title])
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

const TONES: Record<string, string> = {
  approved: 'success', active: 'success', confirmed: 'success', completed: 'success', analyzed: 'success', final: 'success', ready: 'success',
  pending: 'warning', requested: 'warning', draft: 'neutral', uploaded: 'info',
  rejected: 'danger', declined: 'danger', disabled: 'danger', analysis_failed: 'danger', failed: 'danger', error: 'danger',
  cancelled: 'neutral', ended: 'neutral', not_configured: 'warning',
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  return <span className={`badge badge-${TONES[status] ?? 'neutral'}`}>{label ?? titleCase(status)}</span>
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state" role="status">
      <LoaderCircle size={22} className="spin" aria-hidden />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const offline = error instanceof ApiError && error.status === 0
  const message = error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div className="state state-error" role="alert">
      {offline ? <WifiOff size={22} aria-hidden /> : <CircleAlert size={22} aria-hidden />}
      <span>{message}</span>
      {onRetry && <Button variant="secondary" icon={<RefreshCw size={16} />} onClick={onRetry}>Try again</Button>}
    </div>
  )
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      {icon && <div className="empty-icon" aria-hidden>{icon}</div>}
      <p className="empty-title">{title}</p>
      {children && <div className="empty-body">{children}</div>}
    </div>
  )
}

export function Notice({ tone = 'info', title, children }: { tone?: 'info' | 'warning' | 'danger'; title?: string; children: ReactNode }) {
  const Icon = tone === 'info' ? Info : tone === 'warning' ? TriangleAlert : CircleAlert
  return (
    <div className={`notice notice-${tone}`} role={tone === 'danger' ? 'alert' : undefined}>
      <Icon size={18} aria-hidden className="notice-icon" />
      <div>
        {title && <p className="notice-title">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}

export function MedicalDisclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <Notice tone="warning" title={compact ? undefined : 'Experimental decision-support tool'}>
      MedAI is not a medical device and does not provide diagnoses. AI outputs may be wrong and must be
      reviewed by a qualified radiologist or clinician. In an emergency, contact your local emergency services.
    </Notice>
  )
}

/** Accessible modal dialog built on the native <dialog> element (focus trap + Esc handled by the browser). */
export function Dialog({ open, title, onClose, children, footer }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal?.()
    if (!open && el.open) el.close?.()
  }, [open])
  const titleId = useId()
  return (
    <dialog ref={ref} className="dialog" aria-labelledby={titleId} onClose={onClose} onCancel={onClose}>
      {open && (
        <>
          <h2 id={titleId} className="dialog-title">{title}</h2>
          <div className="dialog-body">{children}</div>
          {footer && <div className="dialog-footer">{footer}</div>}
        </>
      )}
    </dialog>
  )
}

export function Pager({ total, limit, offset, onChange }: { total: number; limit: number; offset: number; onChange: (offset: number) => void }) {
  if (total <= limit) return null
  const page = Math.floor(offset / limit) + 1
  const pages = Math.ceil(total / limit)
  return (
    <nav className="pager" aria-label="Pagination">
      <Button variant="secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>Previous</Button>
      <span className="muted">Page {page} of {pages}</span>
      <Button variant="secondary" disabled={offset + limit >= total} onClick={() => onChange(offset + limit)}>Next</Button>
    </nav>
  )
}

export function Stat({ label, value, icon, to }: { label: string; value: ReactNode; icon?: ReactNode; to?: string }) {
  const body = (
    <>
      {icon && <span className="stat-icon" aria-hidden>{icon}</span>}
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </>
  )
  return to ? <Link className="stat stat-link" to={to}>{body}</Link> : <div className="stat">{body}</div>
}
