export interface LoginSolicitud { email: string; password: string }
export interface TokenRespuesta { access_token: string; token_type: 'bearer'; expires_in: number; debe_cambiar_password: boolean }
export interface UsuarioRespuesta {
  id: string; nombre: string; apellido: string; email: string
  activo: boolean; rol: 'ADMIN' | 'USUARIO'; fecha_creacion: string
}
export interface CambioPasswordContexto { id: string; debe_cambiar_password: true }
export type AuthMe = (UsuarioRespuesta & { debe_cambiar_password: false }) | CambioPasswordContexto
export interface PasswordSolicitud { password_actual: string; password_nueva: string }
export interface ErrorContenido {
  codigo: string; mensaje: string
  detalles?: { campo: string; codigo: string; mensaje: string }[]
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isToken(value: unknown): value is TokenRespuesta {
  return record(value) && typeof value.access_token === 'string' && value.access_token.length > 0
    && value.token_type === 'bearer' && value.expires_in === 900 && typeof value.debe_cambiar_password === 'boolean'
}

export function isPerfil(value: unknown): value is UsuarioRespuesta {
  return record(value) && typeof value.id === 'string'
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.id)
    && ['nombre', 'apellido', 'email', 'fecha_creacion'].every(k => typeof value[k] === 'string' && value[k].length > 0)
    && Number.isFinite(Date.parse(value.fecha_creacion as string))
    && typeof value.activo === 'boolean' && (value.rol === 'ADMIN' || value.rol === 'USUARIO')
}

export function isUsuario(value: unknown): value is UsuarioRespuesta {
  return isPerfil(value) && value.activo === true
}

export function isAuthMe(value: unknown): value is AuthMe {
  if (!record(value)) return false
  if (value.debe_cambiar_password === false) return isUsuario(value)
  return value.debe_cambiar_password === true && typeof value.id === 'string'
    && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.id)
    && Object.keys(value).length === 2
}

export function errorCode(value: unknown): string | undefined {
  return record(value) && record(value.error) && typeof value.error.codigo === 'string'
    ? value.error.codigo : undefined
}
