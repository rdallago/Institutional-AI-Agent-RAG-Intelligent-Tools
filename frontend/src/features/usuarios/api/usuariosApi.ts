import { isPerfil } from '../../../api/contracts'
import { ApiError } from '../../../api/errors'
import type { AuthContextValue } from '../../auth/model/authContext'

export type Estado = 'activos' | 'inactivos' | 'todos'
export interface Consulta { estado: Estado; limite: number; desplazamiento: number }
export interface PerfilDatos { nombre: string; apellido: string; email: string }
export interface CrearPerfilDatos extends PerfilDatos { rol: 'ADMIN' | 'USUARIO'; password_inicial: string }
export function parseConsulta(search: URLSearchParams): Consulta {
  const estado = search.get('estado')
  const integer = (key: string, fallback: number, min: number, max: number) => {
    const raw = search.get(key)
    if (raw === null || !/^\d+$/.test(raw)) return fallback
    const value = Number(raw)
    return Number.isSafeInteger(value) && value >= min && value <= max ? value : fallback
  }
  return {
    estado: estado === 'inactivos' || estado === 'todos' ? estado : 'activos',
    limite: integer('limite', 20, 1, 100),
    desplazamiento: integer('desplazamiento', 0, 0, Number.MAX_SAFE_INTEGER - 100),
  }
}
export function consultaSearch(query: Consulta): string {
  return new URLSearchParams({ estado: query.estado, limite: String(query.limite), desplazamiento: String(query.desplazamiento) }).toString()
}
export const validUuid = (value: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
export function createUsuariosApi(get: AuthContextValue['get'], mutate?: AuthContextValue['mutate']) {
  const write = async (path: string, method: 'POST' | 'PUT' | 'DELETE' | 'PATCH', body: unknown, signal: AbortSignal, status: number) => {
    if (!mutate) throw new Error('Falta el transporte autenticado.')
    return mutate(path, method, body, signal, status)
  }
  const validate = (data: unknown, id?: string) => {
    if (!isPerfil(data) || (id && data.id.toLowerCase() !== id.toLowerCase())) throw new ApiError('contract')
    return data
  }
  const pathFor = (id: string) => {
    if (!validUuid(id)) throw new ApiError('http', 404)
    return `/usuarios/${id}`
  }
  return {
    async listar(query: Consulta, signal: AbortSignal) {
      const data = await get('/usuarios', signal, { ...query })
      if (!Array.isArray(data) || data.length > query.limite || !data.every(isPerfil)) throw new ApiError('contract')
      return data
    },
    async obtener(id: string, signal: AbortSignal) {
      if (!validUuid(id)) throw new ApiError('http', 404)
      const data = await get(`/usuarios/${id}`, signal)
      if (!isPerfil(data) || data.id.toLowerCase() !== id.toLowerCase()) throw new ApiError('contract')
      return data
    },
    async crear(input: CrearPerfilDatos, signal: AbortSignal) {
      const user = validate(await write('/usuarios', 'POST', { nombre: input.nombre, apellido: input.apellido, email: input.email, rol: input.rol, password_inicial: input.password_inicial }, signal, 201))
      if (!user.activo || user.rol !== input.rol) throw new ApiError('contract')
      return user
    },
    async editar(id: string, input: PerfilDatos, signal: AbortSignal) {
      return validate(await write(pathFor(id), 'PUT', { nombre: input.nombre, apellido: input.apellido, email: input.email }, signal, 200), id)
    },
    async asignarInicial(id: string, password_inicial: string, signal: AbortSignal) {
      await write(pathFor(id) + '/credencial-inicial', 'POST', { password_inicial }, signal, 204)
    },
    async baja(id: string, signal: AbortSignal) {
      await write(pathFor(id), 'DELETE', undefined, signal, 204)
    },
    async reactivar(id: string, signal: AbortSignal) {
      const user = validate(await write(pathFor(id) + '/reactivar', 'PATCH', undefined, signal, 200), id)
      if (!user.activo) throw new ApiError('contract')
      return user
    },
  }
}
