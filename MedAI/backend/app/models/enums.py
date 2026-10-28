import enum


class UserRole(str, enum.Enum):
    patient = "patient"
    doctor = "doctor"
    admin = "admin"


class AccountStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class DoctorProfileStatus(str, enum.Enum):
    draft = "draft"          # being edited by the doctor, not yet submitted
    pending = "pending"      # submitted, awaiting administrator review
    approved = "approved"    # visible in the patient directory
    rejected = "rejected"    # rejected; doctor may edit and resubmit


class AssignmentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"  # withdrawn by the patient while pending
    ended = "ended"          # an approved assignment ended by an administrator


class AppointmentStatus(str, enum.Enum):
    requested = "requested"
    confirmed = "confirmed"
    declined = "declined"
    cancelled = "cancelled"
    completed = "completed"


class UploadStatus(str, enum.Enum):
    uploaded = "uploaded"
    analyzed = "analyzed"
    analysis_failed = "analysis_failed"


class AnalysisStatus(str, enum.Enum):
    completed = "completed"
    failed = "failed"


class ReviewAgreement(str, enum.Enum):
    agree = "agree"
    partially_agree = "partially_agree"
    disagree = "disagree"
    not_applicable = "not_applicable"  # e.g. no AI analysis was available


class ReviewStatus(str, enum.Enum):
    draft = "draft"
    final = "final"
