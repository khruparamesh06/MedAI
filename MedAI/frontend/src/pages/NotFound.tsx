import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { homePathFor } from '../utils/validation'

export function NotFound() {
  const { user } = useAuth()
  useEffect(() => { document.title = 'Page not found · MedAI' }, [])
  return (
    <div className="fullpage-message">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p className="muted">The page you were looking for does not exist or you do not have access to it.</p>
      <Link className="btn btn-primary" to={user ? homePathFor(user.role) : '/'}>{user ? 'Back to overview' : 'Go to sign in'}</Link>
    </div>
  )
}
