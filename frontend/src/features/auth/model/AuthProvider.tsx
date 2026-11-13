import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { API_BASE_URL } from '../../../app/config'
import type { AuthMe, LoginSolicitud, PasswordSolicitud } from '../../../api/contracts'
import { ApiError } from '../../../api/errors'
import { createHttpClient } from '../../../api/httpClient'
import type { RequestOptions } from '../../../api/httpClient'
import { createAuthApi } from '../api/authApi'
import { authReducer, initialState } from './authState'
import { AuthContext } from './authContext'
import type { SessionNotice } from './authContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState)
  const [notice, setNotice] = useState<SessionNotice | null>(null)
  const token = useRef<string | null>(null)
  const generation = useRef(0)
  const requests = useRef(new Set<AbortController>())
  const pendingLogin = useRef(false)
  const pendingRefresh = useRef(false)
  const authenticated = useRef(false)
  const restricted = useRef(false)
  const pendingChange = useRef(false)
  const closing = useRef(false)
  const expiresAt = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearSession = useCallback(() => {
    generation.current += 1
    for (const request of requests.current) request.abort()
    requests.current.clear()
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
    token.current = null
    expiresAt.current = 0
    authenticated.current = false
    restricted.current = false
    pendingChange.current = false
    pendingLogin.current = false
    pendingRefresh.current = false
  }, [])

  const expire = useCallback(() => {
    const changing = pendingChange.current
    clearSession()
    dispatch({ type: 'reset' })
    setNotice({ severity: 'warning', message: changing
      ? 'La sesión terminó durante el cambio. Puede haberse aplicado. Ingresá nuevamente y verificá tu contraseña.'
      : 'Tu sesión venció o dejó de ser válida. Ingresá nuevamente.' })
  }, [clearSession])

  const acceptContext = useCallback((context: AuthMe) => {
    if (context.debe_cambiar_password && authenticated.current) {
      // Retirar datos normales y respuestas pendientes sin promover el token.
      generation.current += 1
      for (const request of requests.current) request.abort()
      requests.current.clear()
      pendingRefresh.current = false
      pendingChange.current = false
    }
    authenticated.current = !context.debe_cambiar_password
    restricted.current = context.debe_cambiar_password
    dispatch({ type: 'success', user: context })
  }, [])

  const refreshProfile = useCallback(async () => {
    if ((!authenticated.current && !restricted.current) || closing.current || pendingRefresh.current) return
    if (Date.now() >= expiresAt.current) { expire(); return }
    const current = generation.current
    const controller = new AbortController()
    requests.current.add(controller)
    pendingRefresh.current = true
    const api = createAuthApi(createHttpClient(API_BASE_URL, () => token.current))
    try {
      const user = await api.me(controller.signal)
      if (current !== generation.current || controller.signal.aborted) return
      if (Date.now() >= expiresAt.current) { expire(); return }
      if (restricted.current && !user.debe_cambiar_password) { expire(); return }
      acceptContext(user)
      setNotice(null)
    } catch (error) {
      if (current !== generation.current || controller.signal.aborted) return
      // Todo 401 de me es terminal; el 401 de password se trata por separado.
      if (error instanceof ApiError && error.status === 401) {
        expire()
      } else {
        setNotice({ severity: 'error', message: error instanceof ApiError && error.status === 403
          ? 'No tenés permiso para realizar esta consulta.'
          : 'No pudimos actualizar tu perfil. Se muestran los últimos datos verificados; intentá nuevamente.' })
      }
    } finally {
      requests.current.delete(controller)
      if (current === generation.current) pendingRefresh.current = false
    }
  }, [acceptContext, expire])

  useEffect(() => {
    const check = () => {
      if (closing.current || !token.current) return
      if (Date.now() >= expiresAt.current) expire()
      else void refreshProfile()
    }
    const visible = () => { if (document.visibilityState === 'visible') check() }
    window.addEventListener('focus', check)
    document.addEventListener('visibilitychange', visible)
    return () => {
      window.removeEventListener('focus', check)
      document.removeEventListener('visibilitychange', visible)
      clearSession()
    }
  }, [clearSession, expire, refreshProfile])

  const login = useCallback(async (input: LoginSolicitud) => {
    if (pendingLogin.current || closing.current || authenticated.current || restricted.current) return
    clearSession()
    pendingLogin.current = true
    const current = generation.current
    const startedAt = Date.now()
    const controller = new AbortController()
    requests.current.add(controller)
    dispatch({ type: 'start' })
    setNotice(null)
    const api = createAuthApi(createHttpClient(API_BASE_URL, () => token.current))
    const active = () => generation.current === current && !controller.signal.aborted
    try {
      const result = await api.login(input, controller.signal)
      if (!active()) throw new ApiError('cancelled')
      token.current = result.access_token
      expiresAt.current = startedAt + result.expires_in * 1000
      const remaining = expiresAt.current - Date.now()
      if (remaining <= 0) { expire(); throw new ApiError('cancelled') }
      timer.current = setTimeout(expire, remaining)
      dispatch({ type: 'validate' })
      const user = await api.me(controller.signal)
      if (!active()) throw new ApiError('cancelled')
      if (Date.now() >= expiresAt.current) { expire(); throw new ApiError('cancelled') }
      if (result.debe_cambiar_password && !user.debe_cambiar_password) throw new ApiError('contract')
      acceptContext(user)
    } catch (error) {
      if (active()) {
        const provisional = token.current
        clearSession()
        dispatch({ type: 'reset' })
        // Best effort revocation after a failed me. No private identity is exposed.
        if (provisional) {
          const cleanup = new AbortController()
          requests.current.add(cleanup)
          const timeout = setTimeout(() => cleanup.abort(), 5000)
          try {
            await createAuthApi(createHttpClient(API_BASE_URL, () => provisional)).logout(cleanup.signal)
          } catch { /* Remote session can remain until expiry; no token is persisted. */ }
          finally { clearTimeout(timeout); requests.current.delete(cleanup) }
        }
      }
      throw error
    } finally {
      requests.current.delete(controller)
      if (generation.current === current) pendingLogin.current = false
    }
  }, [acceptContext, clearSession, expire])

  const logout = useCallback(async () => {
    if (closing.current || !token.current) return
    const captured = token.current
    closing.current = true
    clearSession()
    const current = generation.current
    dispatch({ type: 'close' })
    setNotice(null)
    const controller = new AbortController()
    requests.current.add(controller)
    const timeout = setTimeout(() => controller.abort(), 5000)
    let outcome: SessionNotice = { severity: 'success', message: 'Sesión cerrada. El servidor confirmó la revocación.' }
    try {
      await createAuthApi(createHttpClient(API_BASE_URL, () => captured)).logout(controller.signal)
    } catch (error) {
      outcome = error instanceof ApiError && error.status === 401
        ? { severity: 'warning', message: 'Sesión cerrada en este navegador. El servidor ya no acepta ese token.' }
        : { severity: 'warning', message: 'Sesión cerrada en este navegador. No se pudo confirmar la revocación remota; puede seguir vigente hasta expirar.' }
    } finally {
      clearTimeout(timeout)
      requests.current.delete(controller)
      closing.current = false
      if (generation.current === current) {
        dispatch({ type: 'reset' })
        setNotice(outcome)
      }
    }
  }, [clearSession])

  const changePassword = useCallback(async (input: PasswordSolicitud) => {
    if (pendingChange.current || closing.current || (!authenticated.current && !restricted.current)) throw new ApiError('cancelled')
    if (Date.now() >= expiresAt.current) { expire(); throw new ApiError('cancelled') }
    pendingChange.current = true
    const current = generation.current
    const controller = new AbortController()
    requests.current.add(controller)
    const timeout = setTimeout(() => controller.abort(), 15000)
    try {
      await createAuthApi(createHttpClient(API_BASE_URL, () => token.current)).password(input, controller.signal)
      if (current !== generation.current) throw new ApiError('cancelled')
      clearSession()
      dispatch({ type: 'reset' })
      setNotice({ severity: 'success', message: 'Contraseña cambiada. Ingresá nuevamente con tu nueva contraseña.' })
    } catch (error) {
      if (current !== generation.current) throw new ApiError('cancelled')
      if (error instanceof ApiError && error.status === 401) {
        if (error.code !== 'CREDENCIALES_INVALIDAS') expire()
      } else if (!(error instanceof ApiError) || error.kind === 'network' || error.kind === 'contract'
          || error.kind === 'cancelled' || (error.status ?? 0) >= 500) {
        clearSession()
        dispatch({ type: 'reset' })
        setNotice({ severity: 'warning', message: 'No pudimos confirmar el cambio. Puede haberse aplicado. Ingresá nuevamente; no se reenviará la contraseña automáticamente.' })
      }
      throw error
    } finally {
      clearTimeout(timeout)
      requests.current.delete(controller)
      if (current === generation.current) pendingChange.current = false
    }
  }, [clearSession, expire])

  const requirePasswordChange = useCallback(async () => {
    generation.current += 1
    for (const request of requests.current) request.abort()
    requests.current.clear()
    authenticated.current = false
    restricted.current = true
    pendingRefresh.current = false
    pendingChange.current = false
    dispatch({ type: 'validate' })
    const current = generation.current
    const controller = new AbortController()
    requests.current.add(controller)
    try {
      const context = await createAuthApi(createHttpClient(API_BASE_URL, () => token.current)).me(controller.signal)
      if (current !== generation.current || controller.signal.aborted) return
      if (!context.debe_cambiar_password || Date.now() >= expiresAt.current) { expire(); return }
      acceptContext(context)
    } catch {
      if (current === generation.current) expire()
    } finally { requests.current.delete(controller) }
  }, [acceptContext, expire])

  const protectedRequest = useCallback(async (path: string, signal: AbortSignal, options: RequestOptions) => {
    if (signal.aborted) throw new ApiError('cancelled')
    if (!authenticated.current || closing.current) throw new ApiError('cancelled')
    if (Date.now() >= expiresAt.current) { expire(); throw new ApiError('cancelled') }
    const current = generation.current
    const controller = new AbortController()
    const cancel = () => controller.abort()
    signal.addEventListener('abort', cancel, { once: true })
    requests.current.add(controller)
    try {
      const data = await createHttpClient(API_BASE_URL, () => token.current)(path, {
        ...options, authenticated: true, signal: controller.signal,
      })
      if (current !== generation.current || controller.signal.aborted) throw new ApiError('cancelled')
      if (Date.now() >= expiresAt.current) { expire(); throw new ApiError('cancelled') }
      return data
    } catch (error) {
      if (current !== generation.current || controller.signal.aborted) throw new ApiError('cancelled')
      if (error instanceof ApiError && error.status === 401) expire()
      if (error instanceof ApiError && error.status === 403 && error.code === 'CAMBIO_PASSWORD_REQUERIDO') {
        await requirePasswordChange()
        throw new ApiError('cancelled')
      }
      throw error
    } finally {
      signal.removeEventListener('abort', cancel)
      requests.current.delete(controller)
    }
  }, [expire, requirePasswordChange])

  const get = useCallback((path: string, signal: AbortSignal, query?: Record<string, string | number>) =>
    protectedRequest(path, signal, { query }), [protectedRequest])
  const mutate = useCallback((path: string, method: 'POST' | 'PUT' | 'DELETE' | 'PATCH', body: unknown, signal: AbortSignal, expectedStatus: number) =>
    protectedRequest(path, signal, { method, body, expectedStatus }), [protectedRequest])
  const value = useMemo(() => ({ state, notice, login, logout, refreshProfile, changePassword, get, mutate }), [state, notice, login, logout, refreshProfile, changePassword, get, mutate])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
