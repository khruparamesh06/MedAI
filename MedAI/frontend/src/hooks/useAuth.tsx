import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { SESSION_EXPIRED_EVENT, tokenStore } from '../api/client'
import { api, type RegisterInput } from '../api/endpoints'
import type { TokenResponse, User } from '../api/types'

interface AuthState {
  user: User | null
  initializing: boolean
  sessionExpired: boolean
  login: (email: string, password: string) => Promise<User>
  register: (input: RegisterInput) => Promise<User>
  logout: () => void
  setUser: (user: User) => void
  acceptToken: (res: TokenResponse) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [initializing, setInitializing] = useState(() => tokenStore.get() !== null)
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    if (!tokenStore.get()) return
    api.me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setInitializing(false))
  }, [])

  useEffect(() => {
    const onExpired = () => {
      setUser(null)
      setSessionExpired(true)
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, onExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, onExpired)
  }, [])

  const acceptToken = useCallback((res: TokenResponse) => {
    tokenStore.set(res.access_token)
    setUser(res.user)
    setSessionExpired(false)
  }, [])

  const value = useMemo<AuthState>(() => ({
    user,
    initializing,
    sessionExpired,
    setUser,
    acceptToken,
    login: async (email, password) => {
      const res = await api.login(email, password)
      acceptToken(res)
      return res.user
    },
    register: async (input) => {
      const res = await api.register(input)
      acceptToken(res)
      return res.user
    },
    logout: () => {
      // Revoke the token on the server too; sign out locally even if the request fails.
      if (tokenStore.get()) api.logout().catch(() => {})
      tokenStore.clear()
      setUser(null)
    },
  }), [user, initializing, sessionExpired, acceptToken])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
