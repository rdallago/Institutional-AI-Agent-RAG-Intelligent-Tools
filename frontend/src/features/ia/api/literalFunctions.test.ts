import { describe, expect, it, vi } from 'vitest'
import { parseAgentResponse } from './iaApi'
import { createConversationsApi } from './conversationsApi'

const answer = 'Función ficticia con cita [F1].\n'.repeat(160)
const result = { respuesta: answer, estrategia: 'RAG', estado: 'FUNDAMENTADA',
  finalizacion: 'completa', fuentes: [{ id: 'F1', pagina: 12 }, { id: 'F2', pagina: 13 }, { id: 'F3', pagina: 14 }] }

describe('transcripción documental extensa', () => {
  it('acepta la respuesta completa y conserva fuentes sin ampliar generación directa', () => {
    expect(answer.length).toBeGreaterThan(4096)
    expect(parseAgentResponse(result).respuesta).toBe(answer)
    expect(() => parseAgentResponse({ ...result, estrategia: 'LLM_DIRECTO', estado: 'GENERADA', fuentes: [] })).toThrow()
    expect(() => parseAgentResponse({ ...result, respuesta: 'x'.repeat(8193) })).toThrow()
    expect(() => parseAgentResponse({ ...result, respuesta: '\u0000' + answer })).toThrow()
  })
  it('recarga íntegramente el historial documental autorizado', async () => {
    const message = { id: 2, rol: 'assistant', contenido: answer, estrategia: 'RAG', estado: 'FUNDAMENTADA',
      herramienta: null, creado_at: '2026-11-12T12:00:00Z', fuentes: result.fuentes }
    const get = vi.fn().mockResolvedValue([message])
    const api = createConversationsApi(get, vi.fn())
    const history = await api.history('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', new AbortController().signal)
    expect(history[0].contenido).toBe(answer)
    get.mockResolvedValue([{ ...message, rol: 'user' }])
    await expect(api.history('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', new AbortController().signal)).rejects.toThrow()
  })
})
