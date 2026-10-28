// TypeScript mirrors of backend/app/schemas. Keep field names identical to the API contract.

export type Role = 'patient' | 'doctor' | 'admin'
export type AccountStatus = 'active' | 'disabled'
export type DoctorProfileStatus = 'draft' | 'pending' | 'approved' | 'rejected'
export type AssignmentStatus = 'pending' | 'approved' | 'rejected' | 'cancelled' | 'ended'
export type AppointmentStatus = 'requested' | 'confirmed' | 'declined' | 'cancelled' | 'completed'
export type UploadStatus = 'uploaded' | 'analyzed' | 'analysis_failed'
export type ReviewAgreement = 'agree' | 'partially_agree' | 'disagree' | 'not_applicable'
export type ReviewStatus = 'draft' | 'final'
export type Sex = 'female' | 'male' | 'other' | 'prefer_not_to_say'

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface User {
  id: number
  email: string
  full_name: string
  role: Role
  status: AccountStatus
  date_of_birth: string | null
  sex: Sex | null
  phone: string | null
  must_change_password: boolean
  created_at: string
}

export interface UserBrief {
  id: number
  full_name: string
  email: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: User
}

export interface AvailabilitySlot {
  weekday: number
  start_time: string
  end_time: string
}

export interface DoctorProfile {
  id: number
  user_id: number
  specialty: string
  license_number: string
  years_experience: number
  bio: string
  clinic_location: string
  status: DoctorProfileStatus
  review_note: string | null
  submitted_at: string | null
  reviewed_at: string | null
  availability: AvailabilitySlot[]
}

export interface DoctorPublic {
  user_id: number
  full_name: string
  specialty: string
  years_experience: number
  bio: string
  clinic_location: string
  availability: AvailabilitySlot[]
}

export interface DoctorAdmin {
  user: User
  profile: DoctorProfile
}

export interface Assignment {
  id: number
  patient: UserBrief
  doctor: UserBrief
  status: AssignmentStatus
  request_reason: string
  decision_note: string | null
  decided_at: string | null
  created_at: string
}

export interface Appointment {
  id: number
  patient: UserBrief
  doctor: UserBrief
  scheduled_at: string
  duration_minutes: number
  reason: string
  status: AppointmentStatus
  doctor_note: string | null
  created_at: string
}

export interface Finding {
  label: string
  display_name: string
  score: number
  above_operating_threshold: boolean | null
}

export interface Analysis {
  id: number
  upload_id: number
  status: 'completed' | 'failed'
  model_name: string
  model_version: string
  weights_sha256: string | null
  score_type: string
  score_description: string | null
  findings: Finding[]
  preprocessing: Record<string, unknown>
  error_message: string | null
  duration_ms: number | null
  created_at: string
}

export interface Review {
  id: number
  upload_id: number
  analysis_id: number | null
  doctor: UserBrief
  findings: string
  impression: string
  recommendation: string
  ai_agreement: ReviewAgreement
  status: ReviewStatus
  created_at: string
  updated_at: string
}

export interface Xray {
  id: number
  owner_id: number
  original_filename: string
  content_type: string
  size_bytes: number
  width: number
  height: number
  view_position: string | null
  patient_note: string | null
  status: UploadStatus
  created_at: string
  latest_analysis: Analysis | null
  review_count: number
}

export interface XrayDetail extends Xray {
  owner: UserBrief
  analyses: Analysis[]
  reviews: Review[]
}

export interface ModelStatus {
  available: boolean
  state: 'ready' | 'not_configured' | 'error'
  reason: string
  model_name: string | null
  model_version: string | null
  backend: string | null
  labels: string[]
  score_type: string | null
  score_description: string | null
  weights_sha256: string | null
  device: string | null
  source: string | null
}

export interface Note {
  id: number
  patient_id: number
  doctor: UserBrief
  body: string
  visible_to_patient: boolean
  created_at: string
}

export interface PatientSummary {
  patient: User
  assignment_id: number
  assigned_since: string | null
  xray_count: number
  pending_review_count: number
  next_appointment: string | null
}

export interface PatientRecord {
  patient: User
  xrays: Xray[]
  notes: Note[]
  appointments: Appointment[]
}

export interface AuditEvent {
  id: number
  actor_id: number | null
  action: string
  entity_type: string
  entity_id: number | null
  detail: Record<string, unknown>
  created_at: string
}

export interface AdminStats {
  patients: number
  doctors_approved: number
  doctors_pending: number
  assignments_pending: number
  appointments_upcoming: number
  xrays_total: number
  analyses_total: number
  model_available: boolean
}

export interface Health {
  status: string
  app: string
  environment: string
  clinic_timezone: string
}
