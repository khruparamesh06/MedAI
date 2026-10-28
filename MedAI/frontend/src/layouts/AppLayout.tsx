import {
  CalendarClock, ClipboardCheck, ClipboardList, FileText, HeartPulse, House, LayoutDashboard, LogOut, Menu,
  ScrollText, Settings, Stethoscope, Upload, UserCheck, UserCog, Users, X,
} from 'lucide-react'
import { useState, type ComponentType } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../hooks/useAuth'

type NavItem = { to: string; label: string; icon: ComponentType<{ size?: number }>; end?: boolean }

const NAV: Record<Role, NavItem[]> = {
  patient: [
    { to: '/patient', label: 'Overview', icon: House, end: true },
    { to: '/patient/xrays/new', label: 'Upload X-ray', icon: Upload },
    { to: '/patient/xrays', label: 'X-ray history', icon: ClipboardList, end: true },
    { to: '/patient/doctors', label: 'Find a doctor', icon: Stethoscope },
    { to: '/patient/appointments', label: 'Appointments', icon: CalendarClock },
    { to: '/patient/records', label: 'Medical record', icon: FileText },
  ],
  doctor: [
    { to: '/doctor', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/doctor/patients', label: 'My patients', icon: Users },
    { to: '/doctor/appointments', label: 'Appointments', icon: CalendarClock },
    { to: '/doctor/profile', label: 'Profile & availability', icon: UserCog },
  ],
  admin: [
    { to: '/admin', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/admin/doctors', label: 'Doctor approvals', icon: UserCheck },
    { to: '/admin/assignments', label: 'Assignment requests', icon: ClipboardCheck },
    { to: '/admin/appointments', label: 'Appointments', icon: CalendarClock },
    { to: '/admin/users', label: 'Accounts', icon: Users },
    { to: '/admin/audit', label: 'Activity log', icon: ScrollText },
  ],
}

const ROLE_LABEL: Record<Role, string> = { patient: 'Patient', doctor: 'Doctor', admin: 'Administrator' }

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  if (!user) return null

  const signOut = () => {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="topbar">
        <button className="icon-button menu-toggle" onClick={() => setMenuOpen((o) => !o)}
          aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen} aria-controls="sidebar">
          {menuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
        <NavLink to="/" className="brand"><HeartPulse size={22} aria-hidden /> MedAI</NavLink>
        <div className="topbar-user">
          <div className="topbar-name">
            <span>{user.full_name}</span>
            <span className="muted small">{ROLE_LABEL[user.role]}</span>
          </div>
          <NavLink to="/account" className="icon-button" aria-label="Account settings" title="Account settings"><Settings size={18} /></NavLink>
          <button className="icon-button" onClick={signOut} aria-label="Sign out" title="Sign out"><LogOut size={18} /></button>
        </div>
      </header>
      <nav id="sidebar" className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`} aria-label="Main navigation">
        {NAV[user.role].map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={() => setMenuOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <Icon size={18} />
            <span>{label}</span>
          </NavLink>
        ))}
        <div className="sidebar-foot small muted">Experimental decision-support software. Not a diagnostic device.</div>
      </nav>
      {menuOpen && <div className="scrim" onClick={() => setMenuOpen(false)} aria-hidden />}
      <main id="main" className="content" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
