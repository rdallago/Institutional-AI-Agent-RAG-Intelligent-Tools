import { createContext, useContext } from 'react'
import type { LoginSolicitud, PasswordSolicitud } from '../../../api/contracts'
import type { AuthState } from './authState'

export interface SessionNotice { severity: 'success' | 'warning' | 'error'; message: string }
export interface AuthContextValue {
  state: AuthState
  notice: SessionNotice | null
  login: (input: LoginSolicitud) => Promise<void>
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
  changePassword: (input: PasswordSolicitud) => Promise<void>
  get: (path: string, signal: AbortSignal, query?: Record<string, string | number>) => Promise<unknown>
  mutate: (path: string, method: 'POST' | 'PUT' | 'DELETE' | 'PATCH', body: unknown, signal: AbortSignal, expectedStatus: number) => Promise<unknown>
}
export const AuthContext = createContext<AuthContextValue | null>(null)
export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('Falta el proveedor de autenticación.')
  return value
}
