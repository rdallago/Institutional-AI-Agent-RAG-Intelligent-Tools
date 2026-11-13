import { errorCode } from './contracts'
import { ApiError } from './errors'

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  body?: unknown
  signal?: AbortSignal
  authenticated?: boolean
  expectedStatus?: number
  query?: Record<string, string | number>
}

export function createHttpClient(base: string, readToken: () => string | null) {
  if (base !== '/api/v1') throw new Error('Destino de API no permitido.')
  return async function request(path: string, options: RequestOptions = {}): Promise<unknown> {
    if (!/^\/[a-zA-Z0-9-]+(?:\/[a-zA-Z0-9-]+)*$/.test(path)) throw new Error('Ruta de API no permitida.')
    const search = new URLSearchParams()
    for (const [key, value] of Object.entries(options.query ?? {})) search.set(key, String(value))
    const headers = new Headers({ Accept: 'application/json' })
    if (options.body !== undefined) headers.set('Content-Type', 'application/json')
    if (options.authenticated) {
      const token = readToken()
      if (!token) throw new ApiError('http', 401, 'AUTENTICACION_REQUERIDA')
      headers.set('Authorization', `Bearer ${token}`)
    }
    let response: Response
    try {
      response = await fetch(base + path + (search.size ? `?${search}` : ''), {
        method: options.method ?? 'GET', headers,
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        signal: options.signal, credentials: 'omit', cache: 'no-store', redirect: 'error',
      })
    } catch {
      throw new ApiError(options.signal?.aborted ? 'cancelled' : 'network')
    }
    if (response.ok && options.expectedStatus !== undefined && response.status !== options.expectedStatus) throw new ApiError('contract')
    if (response.status === 204 && response.ok) return undefined
    let data: unknown
    try { data = await response.json() } catch {
      if (options.signal?.aborted) throw new ApiError('cancelled')
      if (response.ok) throw new ApiError('contract')
    }
    if (!response.ok) {
      const raw = response.headers.get('Retry-After')
      const seconds = raw && /^\d+$/.test(raw) ? Number(raw) : undefined
      const envelope = typeof data === 'object' && data !== null && 'error' in data ? data.error : null
      const fields = typeof envelope === 'object' && envelope !== null && 'detalles' in envelope && Array.isArray(envelope.detalles)
        ? envelope.detalles.flatMap(detail => typeof detail === 'object' && detail !== null && 'campo' in detail
          && typeof detail.campo === 'string' && ['body.nombre', 'body.apellido', 'body.email', 'body.rol', 'body.password_inicial', 'body.password_nueva', 'body.password_actual', 'body.prompt'].includes(detail.campo) ? [detail.campo.slice(5)] : []) : []
      const userId = typeof envelope === 'object' && envelope !== null && 'usuario_id' in envelope
        && typeof envelope.usuario_id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(envelope.usuario_id)
        ? envelope.usuario_id : undefined
      throw new ApiError('http', response.status, errorCode(data),
        seconds !== undefined && Number.isSafeInteger(seconds) ? seconds : undefined, fields, userId)
    }
    return data
  }
}

export type HttpClient = ReturnType<typeof createHttpClient>
