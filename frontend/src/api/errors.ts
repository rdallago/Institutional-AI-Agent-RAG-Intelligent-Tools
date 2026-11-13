export type FailureKind = 'http' | 'network' | 'cancelled' | 'contract'

export class ApiError extends Error {
  constructor(
    public readonly kind: FailureKind,
    public readonly status?: number,
    public readonly code?: string,
    public readonly retryAfter?: number,
    public readonly fields: string[] = [],
    public readonly userId?: string,
  ) { super('La solicitud no pudo completarse.'); this.name = 'ApiError' }
}

export function loginErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'No pudimos completar el ingreso. Intentá nuevamente.'
  if (error.kind === 'network') return 'No pudimos conectar con el servidor. Revisá la conexión e intentá nuevamente.'
  if (error.kind === 'contract') return 'El servidor devolvió una respuesta inesperada. Intentá nuevamente más tarde.'
  if (error.status === 401) return 'No se pudo iniciar sesión con las credenciales proporcionadas.'
  if (error.status === 422) return 'Revisá el email y la contraseña. La solicitud contiene datos inválidos.'
  if (error.status === 429) return 'Demasiados intentos. Esperá antes de volver a intentar.'
  return 'El servicio no está disponible en este momento. Intentá nuevamente más tarde.'
}
