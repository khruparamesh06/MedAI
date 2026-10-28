// Client-side form checks. They mirror the backend rules for fast feedback; the server always re-validates.
import type { Role, Sex, Xray } from '../api/types'
import { WEEKDAYS, formatBytes, isoDate } from './format'

export interface RegisterForm {
  full_name: string
  email: string
  password: string
  confirm: string
  date_of_birth: string
  sex: '' | Sex
  phone: string
}

export function validateRegistration(f: RegisterForm): Record<string, string> {
  const errors: Record<string, string> = {}
  if (f.full_name.trim().length < 2) errors.full_name = 'Enter your full name.'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim())) errors.email = 'Enter a valid email address.'
  if (f.password.length < 10) errors.password = 'Use at least 10 characters.'
  else if (/^[A-Za-z]+$/.test(f.password) || /^\d+$/.test(f.password)) errors.password = 'Mix letters with numbers or symbols.'
  if (f.confirm !== f.password) errors.confirm = 'Passwords do not match.'
  if (f.date_of_birth && f.date_of_birth > isoDate(new Date())) errors.date_of_birth = 'Date of birth must be in the past.'
  return errors
}

export const MAX_UPLOAD_MB = 10
const ACCEPTED_TYPES = ['image/png', 'image/jpeg']

export function checkFile(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type) && !/\.(png|jpe?g)$/i.test(file.name)) return 'Please choose a PNG or JPEG image.'
  if (file.size === 0) return 'This file is empty.'
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `File is too large (${formatBytes(file.size)}). The maximum is ${MAX_UPLOAD_MB} MB.`
  return null
}

export function validateSlots(slots: { weekday: number; start_time: string; end_time: string }[]): string | null {
  for (const s of slots) if (!s.start_time || !s.end_time || s.start_time >= s.end_time) return `${WEEKDAYS[s.weekday]}: start time must be before end time.`
  for (let d = 0; d < 7; d++) {
    const day = slots.filter((s) => s.weekday === d).sort((a, b) => a.start_time.localeCompare(b.start_time))
    for (let i = 1; i < day.length; i++) if (day[i].start_time < day[i - 1].end_time) return `${WEEKDAYS[d]}: time ranges overlap.`
  }
  return null
}

export const homePathFor = (role: Role) => (role === 'admin' ? '/admin' : role === 'doctor' ? '/doctor' : '/patient')

export function analysisLabel(x: Xray): { status: string; label: string } {
  if (x.status === 'analysis_failed') return { status: 'failed', label: 'Analysis failed' }
  if (x.latest_analysis?.status === 'completed') return { status: 'analyzed', label: 'AI scores available' }
  return { status: 'uploaded', label: 'Not analysed' }
}
