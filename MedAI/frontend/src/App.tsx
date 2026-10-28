import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireRole } from './components/RequireRole'
import { AppLayout } from './layouts/AppLayout'
import { AccountPage } from './pages/AccountPage'
import { AdminAppointments } from './pages/admin/AdminAppointments'
import { AdminAssignments } from './pages/admin/AdminAssignments'
import { AdminAudit } from './pages/admin/AdminAudit'
import { AdminDashboard } from './pages/admin/AdminDashboard'
import { AdminDoctors } from './pages/admin/AdminDoctors'
import { AdminUsers } from './pages/admin/AdminUsers'
import { AppointmentsPage } from './pages/AppointmentsPage'
import { DoctorDashboard } from './pages/doctor/DoctorDashboard'
import { DoctorPatientReview } from './pages/doctor/DoctorPatientReview'
import { DoctorPatients } from './pages/doctor/DoctorPatients'
import { DoctorProfilePage } from './pages/doctor/DoctorProfilePage'
import { NotFound } from './pages/NotFound'
import { DoctorDetail } from './pages/patient/DoctorDetail'
import { DoctorDirectory } from './pages/patient/DoctorDirectory'
import { MedicalRecord } from './pages/patient/MedicalRecord'
import { PatientDashboard } from './pages/patient/PatientDashboard'
import { XrayHistory } from './pages/patient/XrayHistory'
import { XrayUpload } from './pages/patient/XrayUpload'
import { Landing } from './pages/public/Landing'
import { Register } from './pages/public/Register'
import { XrayResult } from './pages/XrayResult'

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/register" element={<Register />} />

      <Route element={<RequireRole><AppLayout /></RequireRole>}>
        <Route path="/account" element={<AccountPage />} />

        <Route path="/patient" element={<RequireRole roles={['patient']}><PatientDashboard /></RequireRole>} />
        <Route path="/patient/xrays/new" element={<RequireRole roles={['patient']}><XrayUpload /></RequireRole>} />
        <Route path="/patient/xrays" element={<RequireRole roles={['patient']}><XrayHistory /></RequireRole>} />
        <Route path="/patient/xrays/:id" element={<RequireRole roles={['patient']}><XrayResult /></RequireRole>} />
        <Route path="/patient/doctors" element={<RequireRole roles={['patient']}><DoctorDirectory /></RequireRole>} />
        <Route path="/patient/doctors/:id" element={<RequireRole roles={['patient']}><DoctorDetail /></RequireRole>} />
        <Route path="/patient/appointments" element={<RequireRole roles={['patient']}><AppointmentsPage /></RequireRole>} />
        <Route path="/patient/records" element={<RequireRole roles={['patient']}><MedicalRecord /></RequireRole>} />
        <Route path="/patient/profile" element={<Navigate to="/account" replace />} />

        <Route path="/doctor" element={<RequireRole roles={['doctor']}><DoctorDashboard /></RequireRole>} />
        <Route path="/doctor/patients" element={<RequireRole roles={['doctor']}><DoctorPatients /></RequireRole>} />
        <Route path="/doctor/patients/:id" element={<RequireRole roles={['doctor']}><DoctorPatientReview /></RequireRole>} />
        <Route path="/doctor/xrays/:id" element={<RequireRole roles={['doctor']}><XrayResult /></RequireRole>} />
        <Route path="/doctor/appointments" element={<RequireRole roles={['doctor']}><AppointmentsPage /></RequireRole>} />
        <Route path="/doctor/profile" element={<RequireRole roles={['doctor']}><DoctorProfilePage /></RequireRole>} />

        <Route path="/admin" element={<RequireRole roles={['admin']}><AdminDashboard /></RequireRole>} />
        <Route path="/admin/doctors" element={<RequireRole roles={['admin']}><AdminDoctors /></RequireRole>} />
        <Route path="/admin/assignments" element={<RequireRole roles={['admin']}><AdminAssignments /></RequireRole>} />
        <Route path="/admin/appointments" element={<RequireRole roles={['admin']}><AdminAppointments /></RequireRole>} />
        <Route path="/admin/users" element={<RequireRole roles={['admin']}><AdminUsers /></RequireRole>} />
        <Route path="/admin/audit" element={<RequireRole roles={['admin']}><AdminAudit /></RequireRole>} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
