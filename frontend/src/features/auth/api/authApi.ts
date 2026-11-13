import type { LoginSolicitud, PasswordSolicitud } from '../../../api/contracts'
import { isToken, isAuthMe } from '../../../api/contracts'
import { ApiError } from '../../../api/errors'
import type { HttpClient } from '../../../api/httpClient'

export function createAuthApi(request: HttpClient) {
  return {
    async login(input: LoginSolicitud, signal: AbortSignal) {
      const data = await request('/auth/login', { method: 'POST', body: input, signal, expectedStatus: 200 })
      if (!isToken(data)) throw new ApiError('contract')
      return data
    },
    async me(signal: AbortSignal) {
      const data = await request('/auth/me', { authenticated: true, signal, expectedStatus: 200 })
      if (!isAuthMe(data)) throw new ApiError('contract')
      return data
    },
    async logout(signal: AbortSignal) {
      await request('/auth/logout', { method: 'POST', authenticated: true, signal, expectedStatus: 204 })
    },
    async password(input: PasswordSolicitud, signal: AbortSignal) {
      await request('/auth/password', { method: 'PUT', authenticated: true, signal, expectedStatus: 204,
        body: { password_actual: input.password_actual, password_nueva: input.password_nueva } })
    },
  }
}
