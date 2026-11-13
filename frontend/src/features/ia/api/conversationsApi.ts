import { ApiError } from '../../../api/errors'
import type { AuthContextValue } from '../../auth/model/authContext'
import { parseAgentResponse } from './iaApi'
import { textMetrics } from '../model/promptPolicy'

export interface ChatMessage {
  id: number; rol: 'user' | 'assistant'; contenido: string
  estrategia: 'LLM_DIRECTO' | 'RAG' | 'TOOL'; estado: string; herramienta: string | null
  creado_at: string; fuentes: { id: string; pagina: number }[]
}
export interface Conversation { id: string; creado_at: string; actualizado_at: string }
const uuid = (value: unknown): value is string => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value)

export function createConversationsApi(get: AuthContextValue['get'], mutate: AuthContextValue['mutate']) {
  return {
    async list(signal: AbortSignal): Promise<Conversation[]> {
      const value = await get('/ia/conversaciones', signal)
      if (!Array.isArray(value) || value.length > 50 || !value.every(v => v && uuid(v.id)
        && Object.keys(v).sort().join(',') === 'actualizado_at,creado_at,id'
        && typeof v.creado_at === 'string' && typeof v.actualizado_at === 'string')) throw new ApiError('contract')
      return value
    },
    async create(signal: AbortSignal, id: string): Promise<string> {
      if (!uuid(id)) throw new ApiError('contract')
      const value = await mutate('/ia/conversaciones', 'POST', { conversacion_id: id }, signal, 200)
      if (!value || typeof value !== 'object' || Object.keys(value).join(',') !== 'id' || !('id' in value) || !uuid(value.id)) throw new ApiError('contract')
      return value.id
    },
    async history(id: string, signal: AbortSignal): Promise<ChatMessage[]> {
      if (!uuid(id)) throw new ApiError('contract')
      const value = await get(`/ia/conversaciones/${id}/mensajes`, signal)
      if (!Array.isArray(value) || value.length > 100 || !value.every(v => {
        if (!v || Object.keys(v).sort().join(',') !== 'contenido,creado_at,estado,estrategia,fuentes,herramienta,id,rol'
          || !Number.isSafeInteger(v.id) || v.id < 1 || !['user', 'assistant'].includes(v.rol)
          || !['LLM_DIRECTO', 'RAG', 'TOOL'].includes(v.estrategia) || typeof v.estado !== 'string'
          || typeof v.creado_at !== 'string' || ![null, 'consultar_clima'].includes(v.herramienta)
          || typeof v.contenido !== 'string' || !Array.isArray(v.fuentes) || v.fuentes.length > 3) return false
        const m = textMetrics(v.contenido)
        const literalCapacity = v.rol === 'assistant' && v.estrategia === 'RAG'
          && v.estado === 'FUNDAMENTADA' && v.fuentes.length > 0
        return m.unicode && m.nonBlank && !m.nul && m.points <= (literalCapacity ? 8192 : 4096)
          && m.bytes !== null && m.bytes <= (literalCapacity ? 32768 : 16384)
          && v.fuentes.every((f: { id: string; pagina: number }) => f && Object.keys(f).sort().join(',') === 'id,pagina'
            && /^F[1-3]$/.test(f.id) && Number.isSafeInteger(f.pagina) && f.pagina > 0)
      })) throw new ApiError('contract')
      return value
    },
    async turn(id: string, key: string, prompt: string, modo: string, document: string, signal: AbortSignal) {
      if (!uuid(id) || !uuid(key)) throw new ApiError('contract')
      const value = await mutate(`/ia/conversaciones/${id}/mensajes`, 'POST',
        { prompt, modo, solicitud_id: key, ...(document && modo !== 'LLM_DIRECTO' ? { documento_id: document } : {}) }, signal, 200)
      if (!value || typeof value !== 'object' || Object.keys(value).sort().join(',') !== 'conversacion_id,herramienta,resultado,solicitud_id'
        || !('conversacion_id' in value) || value.conversacion_id !== id || !('solicitud_id' in value) || value.solicitud_id !== key
        || !('herramienta' in value) || ![null, 'consultar_clima'].includes(value.herramienta as string | null)
        || !('resultado' in value)) throw new ApiError('contract')
      return parseAgentResponse(value.resultado)
    },
  }
}
