import { request } from './client'
import type {
  AdminStats, Analysis, Appointment, AppointmentStatus, Assignment, AssignmentStatus, AuditEvent,
  AvailabilitySlot, DoctorAdmin, DoctorProfile, DoctorProfileStatus, DoctorPublic, Health, ModelStatus,
  Note, Page, PatientRecord, PatientSummary, Review, ReviewAgreement, ReviewStatus, Role, Sex,
  TokenResponse, User, Xray, XrayDetail,
} from './types'

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const search = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') search.set(k, String(v))
  const s = search.toString()
  return s ? `?${s}` : ''
}

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  date_of_birth?: string | null
  sex?: Sex | null
  phone?: string | null
}

export interface ReviewInput {
  findings: string
  impression: string
  recommendation: string
  ai_agreement: ReviewAgreement
  status: ReviewStatus
  analysis_id: number | null
}

export const api = {
  health: () => request<Health>('/api/health'),

  // auth
  login: (email: string, password: string) => request<TokenResponse>('/api/auth/login', { method: 'POST', json: { email, password } }),
  register: (input: RegisterInput) => request<TokenResponse>('/api/auth/register', { method: 'POST', json: input }),
  me: () => request<User>('/api/auth/me'),
  updateMe: (input: Partial<Pick<User, 'full_name' | 'date_of_birth' | 'sex' | 'phone'>>) =>
    request<User>('/api/auth/me', { method: 'PATCH', json: input }),
  changePassword: (current_password: string, new_password: string) =>
    request<TokenResponse>('/api/auth/change-password', { method: 'POST', json: { current_password, new_password } }),
  logout: () => request<{ detail: string }>('/api/auth/logout', { method: 'POST' }),
  logoutAll: () => request<{ detail: string }>('/api/auth/logout-all', { method: 'POST' }),

  // doctors directory & own profile
  doctors: (params: { q?: string; specialty?: string; limit?: number; offset?: number } = {}) =>
    request<Page<DoctorPublic>>(`/api/doctors${qs(params)}`),
  specialties: () => request<string[]>('/api/doctors/specialties'),
  doctor: (id: number) => request<DoctorPublic>(`/api/doctors/${id}`),
  myDoctorProfile: () => request<DoctorProfile>('/api/doctors/me/profile'),
  updateMyDoctorProfile: (input: Pick<DoctorProfile, 'specialty' | 'license_number' | 'years_experience' | 'bio' | 'clinic_location'>) =>
    request<DoctorProfile>('/api/doctors/me/profile', { method: 'PUT', json: input }),
  updateMyAvailability: (slots: AvailabilitySlot[]) =>
    request<DoctorProfile>('/api/doctors/me/availability', { method: 'PUT', json: { slots } }),
  submitMyDoctorProfile: () => request<DoctorProfile>('/api/doctors/me/profile/submit', { method: 'POST' }),

  // assignments (patient)
  requestAssignment: (doctor_id: number, reason: string) =>
    request<Assignment>('/api/assignments', { method: 'POST', json: { doctor_id, reason } }),
  myAssignments: () => request<Assignment[]>('/api/assignments/mine'),
  cancelAssignment: (id: number) => request<Assignment>(`/api/assignments/${id}/cancel`, { method: 'POST' }),

  // x-rays & AI
  modelStatus: () => request<ModelStatus>('/api/ai/status'),
  uploadXray: (file: File, view_position: string, note: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('view_position', view_position)
    form.append('note', note)
    return request<Xray>('/api/xrays', { method: 'POST', body: form })
  },
  myXrays: (limit = 20, offset = 0) => request<Page<Xray>>(`/api/xrays${qs({ limit, offset })}`),
  xray: (id: number) => request<XrayDetail>(`/api/xrays/${id}`),
  xrayImage: (id: number) => request<Blob>(`/api/xrays/${id}/image`),
  deleteXray: (id: number) => request<void>(`/api/xrays/${id}`, { method: 'DELETE' }),
  analyze: (id: number) => request<Analysis>(`/api/xrays/${id}/analyze`, { method: 'POST' }),
  createReview: (xrayId: number, input: ReviewInput) =>
    request<Review>(`/api/xrays/${xrayId}/reviews`, { method: 'POST', json: input }),
  updateReview: (reviewId: number, input: ReviewInput) =>
    request<Review>(`/api/xrays/reviews/${reviewId}`, { method: 'PUT', json: input }),

  // records
  myRecord: () => request<PatientRecord>('/api/patients/me/record'),

  // appointments
  appointments: (params: { status?: AppointmentStatus; upcoming?: boolean; limit?: number; offset?: number } = {}) =>
    request<Page<Appointment>>(`/api/appointments${qs(params)}`),
  requestAppointment: (input: { doctor_id: number; date: string; start_time: string; reason: string; duration_minutes: number }) =>
    request<Appointment>('/api/appointments', { method: 'POST', json: input }),
  updateAppointment: (id: number, status: Exclude<AppointmentStatus, 'requested'>, note?: string) =>
    request<Appointment>(`/api/appointments/${id}`, { method: 'PATCH', json: { status, note } }),

  // doctor portal
  assignedPatients: () => request<PatientSummary[]>('/api/doctor/patients'),
  reviewQueue: () => request<Xray[]>('/api/doctor/review-queue'),
  patientRecord: (patientId: number) => request<PatientRecord>(`/api/doctor/patients/${patientId}`),
  addNote: (patientId: number, body: string, visible_to_patient: boolean) =>
    request<Note>(`/api/doctor/patients/${patientId}/notes`, { method: 'POST', json: { body, visible_to_patient } }),

  // admin
  adminStats: () => request<AdminStats>('/api/admin/stats'),
  adminUsers: (params: { role?: Role; q?: string; limit?: number; offset?: number } = {}) =>
    request<Page<User>>(`/api/admin/users${qs(params)}`),
  adminSetUserStatus: (id: number, status: 'active' | 'disabled') =>
    request<User>(`/api/admin/users/${id}/status`, { method: 'PATCH', json: { status } }),
  adminDoctors: (status?: DoctorProfileStatus) => request<DoctorAdmin[]>(`/api/admin/doctors${qs({ status })}`),
  adminCreateDoctor: (email: string, full_name: string, temporary_password: string) =>
    request<DoctorAdmin>('/api/admin/doctors', { method: 'POST', json: { email, full_name, temporary_password } }),
  adminDecideDoctor: (profileId: number, approve: boolean, note?: string) =>
    request<DoctorProfile>(`/api/admin/doctors/${profileId}/${approve ? 'approve' : 'reject'}`, { method: 'POST', json: { note } }),
  adminAssignments: (status?: AssignmentStatus, limit = 50, offset = 0) =>
    request<Page<Assignment>>(`/api/admin/assignments${qs({ status, limit, offset })}`),
  adminDecideAssignment: (id: number, action: 'approve' | 'reject' | 'end', note?: string) =>
    request<Assignment>(`/api/admin/assignments/${id}/${action}`, { method: 'POST', json: { note } }),
  adminAudit: (limit = 50, offset = 0) => request<Page<AuditEvent>>(`/api/admin/audit${qs({ limit, offset })}`),
}
