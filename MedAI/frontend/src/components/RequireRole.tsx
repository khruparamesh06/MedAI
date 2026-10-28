import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../hooks/useAuth'
import { homePathFor } from '../utils/validation'
import { LoadingState } from './ui'

/**
 * Client-side route guard for a better experience only. Authorization is enforced by the
 * backend on every request; hiding a page here is never relied on for security.
 */
export function RequireRole({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, initializing } = useAuth()
  const location = useLocation()
  if (initializing) return <LoadingState label="Restoring your session…" />
  if (!user) return <Navigate to="/" replace state={{ from: location.pathname }} />
  if (user.must_change_password && location.pathname !== '/account') return <Navigate to="/account" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to={homePathFor(user.role)} replace />
  return <>{children}</>
}
