import { ApiError } from '../../../api/errors'
import type { AuthContextValue } from '../../auth/model/authContext'
import { textMetrics } from '../model/promptPolicy'

export interface ConsultaIARespuesta { respuesta: string; finalizacion: 'completa' | 'limite' }
export interface RespuestaRAG {
  respuesta: string; finalizacion: 'completa' | 'limite' | null
  estado: 'FUNDAMENTADA' | 'SIN_EVIDENCIA'; estrategia: 'RAG'
  fuentes: { id: string; pagina: number }[]
}

export interface RespuestaDirecta extends ConsultaIARespuesta {
  estado: 'GENERADA'; estrategia: 'LLM_DIRECTO'; fuentes: []
}
export type RespuestaAdaptativa = RespuestaRAG | RespuestaDirecta
export interface RespuestaTool {
  respuesta: string; finalizacion: null; estado: 'HERRAMIENTA' | 'ACLARACION'; estrategia: 'TOOL'
  fuentes: []
}
export interface RespuestaAclaracion {
  respuesta: string; finalizacion: null; estado: 'ACLARACION'; estrategia: 'RAG' | 'LLM_DIRECTO'; fuentes: []
}
export type AgentResponse = RespuestaAdaptativa | RespuestaTool | RespuestaAclaracion

export function parseAgentResponse(value: unknown): AgentResponse {
  if (isRAG(value) || isDirect(value)) return value
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    const v = value as Record<string, unknown>
    if (Object.keys(v).sort().join(',') === 'estado,estrategia,finalizacion,fuentes,respuesta'
      && (v.estrategia === 'RAG' || v.estrategia === 'LLM_DIRECTO') && v.estado === 'ACLARACION'
      && v.finalizacion === null && Array.isArray(v.fuentes) && v.fuentes.length === 0
      && isRespuesta({ respuesta: v.respuesta, finalizacion: 'completa' })) return value as RespuestaAclaracion
    if (Object.keys(v).sort().join(',') === 'estado,estrategia,finalizacion,fuentes,respuesta'
      && v.estrategia === 'TOOL' && (v.estado === 'HERRAMIENTA' || v.estado === 'ACLARACION')
      && v.finalizacion === null && Array.isArray(v.fuentes) && v.fuentes.length === 0
      && isRespuesta({ respuesta: v.respuesta, finalizacion: 'completa' })) return value as RespuestaTool
  }
  throw new ApiError('contract')
}

function isRAG(value: unknown): value is RespuestaRAG {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const v = value as Record<string, unknown>
  if (Object.keys(v).sort().join(',') !== 'estado,estrategia,finalizacion,fuentes,respuesta'
    || v.estrategia !== 'RAG' || typeof v.respuesta !== 'string' || !Array.isArray(v.fuentes)
    || v.fuentes.length > 3) return false
  const m = textMetrics(v.respuesta)
  const literalCapacity = v.estado === 'FUNDAMENTADA' && v.finalizacion === 'completa' && v.fuentes.length > 0
  if (!m.unicode || !m.nonBlank || m.nul || m.points > (literalCapacity ? 8192 : 4096)
    || m.bytes === null || m.bytes > (literalCapacity ? 32768 : 16384)) return false
  if (!v.fuentes.every(f => typeof f === 'object' && f !== null && Object.keys(f).sort().join(',') === 'id,pagina'
    && /^F[1-3]$/.test(f.id) && Number.isSafeInteger(f.pagina) && f.pagina > 0)) return false
  return v.estado === 'SIN_EVIDENCIA' ? v.finalizacion === null && v.fuentes.length === 0
    : v.estado === 'FUNDAMENTADA' && (v.finalizacion === 'completa' || v.finalizacion === 'limite') && v.fuentes.length > 0
}

function isRespuesta(value: unknown): value is ConsultaIARespuesta {
  if (typeof value !== 'object' || value === null || Array.isArray(value) || Object.keys(value).length !== 2
    || !('respuesta' in value) || typeof value.respuesta !== 'string' || !('finalizacion' in value)
    || (value.finalizacion !== 'completa' && value.finalizacion !== 'limite')) return false
  const metrics = textMetrics(value.respuesta)
  return metrics.unicode && metrics.nonBlank && !metrics.nul && metrics.points <= 4096
    && metrics.bytes !== null && metrics.bytes <= 16384
}

function isDirect(value: unknown): value is RespuestaDirecta {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const v = value as Record<string, unknown>
  return Object.keys(v).sort().join(',') === 'estado,estrategia,finalizacion,fuentes,respuesta'
    && v.estrategia === 'LLM_DIRECTO' && v.estado === 'GENERADA'
    && Array.isArray(v.fuentes) && v.fuentes.length === 0
    && isRespuesta({ respuesta: v.respuesta, finalizacion: v.finalizacion })
}

export function createIAApi(mutate: AuthContextValue['mutate']) {
  return {
    async auto(prompt: string, documento_id: string, signal: AbortSignal): Promise<AgentResponse> {
      const data = await mutate('/ia/respuestas', 'POST', { prompt, modo: 'AUTO', ...(documento_id ? { documento_id } : {}) }, signal, 200)
      return parseAgentResponse(data)
    },
    async rag(prompt: string, documento_id: string, signal: AbortSignal): Promise<RespuestaRAG> {
      const data = await mutate('/ia/respuestas', 'POST', { prompt, modo: 'RAG', documento_id }, signal, 200)
      if (!isRAG(data)) throw new ApiError('contract')
      return data
    },
    async consultar(prompt: string, signal: AbortSignal): Promise<ConsultaIARespuesta> {
      const data = await mutate('/ia/consultas', 'POST', { prompt }, signal, 200)
      if (!isRespuesta(data)) throw new ApiError('contract')
      return data
    },
  }
}
