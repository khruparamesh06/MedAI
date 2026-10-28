export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatDateTime(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZone,
  })
}

export const shortTime = (t: string) => t.slice(0, 5)

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

export const titleCase = (s: string) => s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

/** Local calendar date (YYYY-MM-DD) without UTC conversion. */
export function isoDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** Weekday index matching the backend (0 = Monday). */
export const backendWeekday = (dateStr: string) => (new Date(`${dateStr}T12:00:00`).getDay() + 6) % 7

/** Start times every `step` minutes such that [start, start+duration] fits inside a slot. */
export function startTimesWithin(slots: { start_time: string; end_time: string }[], duration: number, step = 15): string[] {
  const toMin = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3, 5))
  const out: string[] = []
  for (const s of slots) {
    for (let m = Math.ceil(toMin(s.start_time) / step) * step; m + duration <= toMin(s.end_time); m += step) {
      out.push(`${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`)
    }
  }
  return Array.from(new Set(out)).sort()
}
