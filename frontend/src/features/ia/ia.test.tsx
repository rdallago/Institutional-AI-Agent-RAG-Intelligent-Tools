import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { expect, it, vi } from 'vitest'
import { AppProviders } from '../../app/providers'
import { AppRoutes } from '../../router/routes'
import { useAuth } from '../auth/model/authContext'
import { server } from '../../test/mocks/server'
import { testToken, testUser } from '../../test/mocks/handlers'
import { validatePrompt, textMetrics } from './model/promptPolicy'
import { createIAApi } from './api/iaApi'

function Controls() {
  const { login, logout, state } = useAuth()
  const navigate = useNavigate()
  return <div><output data-testid="state">{state.status}</output>
    <button onClick={() => { void login({ email: 'ana@example.com', password: 'ficticia' }).catch(() => {}) }}>Acceder ficticio</button>
    <button onClick={() => navigate('/ia')}>Abrir IA</button>
    <button onClick={() => navigate('/dashboard')}>Salir de IA</button>
    <button onClick={() => { void logout() }}>Logout ficticio</button></div>
}
function setup() {
  return render(<AppProviders><MemoryRouter initialEntries={['/ia']}><Controls /><AppRoutes /></MemoryRouter></AppProviders>)
}
async function enter(mode: 'AUTO' | 'LLM_DIRECTO' | 'CHAT' = 'LLM_DIRECTO') {
  fireEvent.click(screen.getByText('Acceder ficticio'))
  await screen.findByRole('heading', { name: /Bienvenido/ })
  fireEvent.click(screen.getAllByRole('link', { name: 'Consultar IA' })[0])
  await screen.findByRole('heading', { name: 'Consultar IA' })
  if (mode === 'CHAT') return
  fireEvent.click(screen.getByText('Diagnóstico sin historial'))
  expect(screen.getByLabelText('Estrategia')).toHaveValue('AUTO')
  if (mode === 'LLM_DIRECTO') fireEvent.change(screen.getByLabelText('Estrategia'), { target: { value: mode } })
}
function send(prompt = 'Consulta ficticia') {
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: prompt } })
  fireEvent.submit(screen.getByLabelText('Consulta').closest('form')!)
}
const success = { respuesta: 'Respuesta ficticia', finalizacion: 'completa' }

it('articulos homonimos muestran aclaracion normativa en conversacion', async () => {
  const id = '11111111-1111-4111-8111-111111111111'
  const answer = 'Indicá la sección: Reglamento Orgánico Marco (página 11); Régimen Académico Marco (página 58).'
  let sent = false
  const handler = vi.fn(async ({ request }: { request: Request }) => {
    const body = await request.json() as { solicitud_id: string }
    sent = true
    return HttpResponse.json({ conversacion_id: id, solicitud_id: body.solicitud_id, herramienta: null,
      resultado: { respuesta: answer, estrategia: 'RAG', estado: 'ACLARACION', finalizacion: null, fuentes: [] } })
  })
  server.use(
    http.get('/api/v1/ia/conversaciones', () => HttpResponse.json([{ id, creado_at: '2026-11-11', actualizado_at: '2026-11-11' }])),
    http.get(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json(sent ? [
      { id: 1, rol: 'assistant', contenido: answer, estrategia: 'RAG', estado: 'ACLARACION',
        herramienta: null, creado_at: '2026-11-11', fuentes: [] },
    ] : [])),
    http.post(`/api/v1/ia/conversaciones/${id}/mensajes`, handler),
  )
  setup(); await enter('CHAT')
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: 'Articulo 24 del reglamento académico' } })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }))
  expect(await screen.findByText(answer)).toBeVisible()
  expect(handler).toHaveBeenCalledTimes(1)
})

it('conversación crea historial, ejecuta tool y recupera tras volver a ingresar', async () => {
  const id = '11111111-1111-4111-8111-111111111111'
  const created = '2026-11-04T10:00:00Z'
  let exists = false
  let messages: unknown[] = []
  const handler = vi.fn(async ({ request }: { request: Request }) => {
    const body = await request.json() as { prompt: string; modo: string; solicitud_id: string }
    expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
    expect(body.modo).toBe('AUTO')
    const answer = 'Esquina: 20 °C. Referencia: fecha ficticia de prueba. Open-Meteo.'
    messages = [
      { id: 1, rol: 'user', contenido: body.prompt, estrategia: 'TOOL', estado: 'HERRAMIENTA', herramienta: 'consultar_clima', creado_at: created, fuentes: [] },
      { id: 2, rol: 'assistant', contenido: answer, estrategia: 'TOOL', estado: 'HERRAMIENTA', herramienta: 'consultar_clima', creado_at: created, fuentes: [] },
    ]
    return HttpResponse.json({ conversacion_id: id, solicitud_id: body.solicitud_id, herramienta: 'consultar_clima',
      resultado: { respuesta: answer, estrategia: 'TOOL', estado: 'HERRAMIENTA', finalizacion: null, fuentes: [] } })
  })
  server.use(
    http.get('/api/v1/ia/conversaciones', () => HttpResponse.json(exists ? [{ id, creado_at: created, actualizado_at: created }] : [])),
    http.post('/api/v1/ia/conversaciones', () => { exists = true; return HttpResponse.json({ id }) }),
    http.get(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json(messages)),
    http.post(`/api/v1/ia/conversaciones/${id}/mensajes`, handler),
  )
  setup(); await enter('CHAT')
  expect(screen.queryByLabelText('Estrategia')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Documento')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: '¿Cómo está el clima en Esquina, Corrientes, Argentina?' } })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }))
  await screen.findByText(/Esquina: 20 °C/)
  expect(screen.queryByText(/Estrategia:|Estado:|Herramienta:/)).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Datos meteorológicos por Open-Meteo' })).toHaveAttribute('href', 'https://open-meteo.com/')
  expect(handler).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('Logout ficticio'))
  await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'))
  await enter('CHAT')
  await screen.findByText(/Esquina: 20 °C/)
  expect(handler).toHaveBeenCalledTimes(1)
})

it('conversación muestra indisponibilidad sin inventar clima', async () => {
  const id = '11111111-1111-4111-8111-111111111111'
  const keys: string[] = []
  server.use(http.get('/api/v1/ia/conversaciones', () => HttpResponse.json([{ id, creado_at: '2026-11-04', actualizado_at: '2026-11-04' }])),
    http.get(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json([])),
    http.post(`/api/v1/ia/conversaciones/${id}/mensajes`, async ({ request }) => {
      const body = await request.json() as { solicitud_id: string }
      keys.push(body.solicitud_id)
      return HttpResponse.json({ error: { codigo: 'IA_NO_DISPONIBLE', mensaje: 'PRIVATE' } }, { status: 503 })
    }))
  setup(); await enter('CHAT')
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: 'Clima en Esquina, Argentina' } })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }))
  await screen.findByText(/proveedor o servicio no está disponible/)
  expect(screen.queryByText('PRIVATE')).not.toBeInTheDocument()
  expect(screen.getByRole('log')).toBeEmptyDOMElement()
  expect(keys).toHaveLength(1)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }))
  await waitFor(() => expect(keys).toHaveLength(2))
  expect(keys[0]).not.toBe(keys[1])
})

it('conversacion distingue timeout sin respuesta reciclada ni reintento', async () => {
  const id = '11111111-1111-4111-8111-111111111111'
  const handler = vi.fn(() => HttpResponse.json({ error: { codigo: 'IA_TIEMPO_AGOTADO', mensaje: 'PRIVATE' } }, { status: 504 }))
  server.use(http.get('/api/v1/ia/conversaciones', () => HttpResponse.json([{ id, creado_at: '2026-11-04', actualizado_at: '2026-11-04' }])),
    http.get(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json([])),
    http.post(`/api/v1/ia/conversaciones/${id}/mensajes`, handler))
  setup(); await enter('CHAT')
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: 'Consulta academica' } })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }))
  await screen.findByText(/Se agotó el tiempo del último envío/)
  expect(screen.queryByText('PRIVATE')).not.toBeInTheDocument()
  expect(screen.getByRole('log')).toBeEmptyDOMElement()
  expect(handler).toHaveBeenCalledTimes(1)
})

it.each([
  ['CLIMA_NO_DISPONIBLE', /Open-Meteo no está disponible/],
  ['IA_PLANIFICADOR_NO_DISPONIBLE', /planificador Qwen\/Ollama no está disponible/],
  ['IA_MEMORIA_INSUFICIENTE', /No hay RAM suficiente/],
])('conversación distingue indisponibilidad %s sin exponer cuerpos', async (code, message) => {
  const id = '11111111-1111-4111-8111-111111111111'
  server.use(http.get('/api/v1/ia/conversaciones', () => HttpResponse.json([{ id, creado_at: '2026-11-04', actualizado_at: '2026-11-04' }])),
    http.get(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json([])),
    http.post(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json({ error: { codigo: code, mensaje: 'PRIVATE' } }, { status: 503 })))
  setup(); await enter('CHAT')
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: 'Consulta de prueba' } })
  await waitFor(() => expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Enviar consulta' }))
  await screen.findByText(message)
  expect(screen.queryByText('PRIVATE')).not.toBeInTheDocument()
})

it('cuota confirmada permite otro envío manual con clave nueva y sin reintento automático', async () => {
  const id = '11111111-1111-4111-8111-111111111111'
  const keys: string[] = []
  server.use(
    http.get('/api/v1/ia/conversaciones', () => HttpResponse.json([{ id, creado_at: '2026-11-04', actualizado_at: '2026-11-04' }])),
    http.get(`/api/v1/ia/conversaciones/${id}/mensajes`, () => HttpResponse.json([])),
    http.post(`/api/v1/ia/conversaciones/${id}/mensajes`, async ({ request }) => {
      const body = await request.json() as { solicitud_id: string }
      keys.push(body.solicitud_id)
      return HttpResponse.json({ error: { codigo: 'IA_LIMITE_INTENTOS', mensaje: 'ficticio' } },
        { status: 429, headers: { 'Retry-After': '1' } })
    }),
  )
  setup(); await enter('CHAT')
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: 'Clima en Esquina, Argentina' } })
  const button = screen.getByRole('button', { name: 'Enviar consulta' })
  await waitFor(() => expect(button).toBeEnabled())
  fireEvent.click(button)
  await screen.findByText(/Alcanzaste la cuota temporal/)
  expect(button).toBeDisabled()
  await waitFor(() => expect(button).toBeEnabled(), { timeout: 2500 })
  expect(keys).toHaveLength(1)
  fireEvent.click(button)
  await waitFor(() => expect(keys).toHaveLength(2))
  expect(keys[1]).not.toBe(keys[0])
})

it.each([
  ['¿Qué es una API REST?', 'LLM_DIRECTO', 'GENERADA'],
  ['¿Qué establece la normativa institucional?', 'RAG', 'SIN_EVIDENCIA'],
] as const)('AUTO predeterminado sin seleccionar documento: %s', async (question, strategy, status) => {
  const handler = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.json()).toEqual({ modo: 'AUTO', prompt: question })
    return HttpResponse.json({ respuesta: status === 'GENERADA' ? 'Respuesta general.' : 'No hay evidencia autorizada.',
      estado: status, estrategia: strategy, finalizacion: status === 'GENERADA' ? 'completa' : null, fuentes: [] })
  })
  server.use(http.post('/api/v1/ia/respuestas', handler))
  setup(); await enter('AUTO')
  expect(screen.getByLabelText('Estrategia')).toHaveValue('AUTO')
  send(question)
  await screen.findByText(`Estrategia: ${strategy}`)
  expect(screen.getByText(`Estado: ${status}`)).toBeVisible()
  expect(handler).toHaveBeenCalledTimes(1)
  expect(screen.queryByText(/Página PDF/)).not.toBeInTheDocument()
})

it.each(['FUNDAMENTADA', 'SIN_EVIDENCIA'])('RAG muestra estrategia, estado y fuentes verificadas: %s', async estado => {
  const id = '11111111-1111-4111-8111-111111111111'
  server.use(http.get('/api/v1/ia/documentos', () => HttpResponse.json([{ id, titulo: 'Reglamento ficticio' }])),
    http.post('/api/v1/ia/respuestas', async ({ request }) => {
      expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
      expect(await request.json()).toEqual({ prompt: 'Consulta ficticia', modo: 'RAG', documento_id: id })
      return HttpResponse.json({ respuesta: estado === 'SIN_EVIDENCIA' ? 'No hay evidencia suficiente.' : 'Norma ficticia [F1].',
        estrategia: 'RAG', estado, finalizacion: estado === 'SIN_EVIDENCIA' ? null : 'completa',
        fuentes: estado === 'SIN_EVIDENCIA' ? [] : [{ id: 'F1', pagina: 12 }] })
    }))
  setup(); await enter()
  fireEvent.change(screen.getByLabelText('Estrategia'), { target: { value: 'RAG' } })
  await screen.findByRole('option', { name: 'Reglamento ficticio' })
  send()
  await screen.findByText(`Estado: ${estado}`)
  expect(screen.getByText('Estrategia: RAG')).toBeInTheDocument()
  if (estado === 'FUNDAMENTADA') expect(screen.getByText('[F1] Página PDF 12')).toBeInTheDocument()
  else expect(screen.queryByText(/Finalización:/)).not.toBeInTheDocument()
})

it('RAG rechaza referencias y campos inesperados del transporte', async () => {
  const mutate = vi.fn().mockResolvedValue({ respuesta: 'Texto', estrategia: 'RAG', estado: 'FUNDAMENTADA',
    finalizacion: 'completa', fuentes: [{ id: 'F999', pagina: 1 }] })
  await expect(createIAApi(mutate).rag('Pregunta', 'id', new AbortController().signal)).rejects.toMatchObject({ kind: 'contract' })
})

it.each(['', ' \n\t', '\u0085', '\0', '\ud800', 'a'.repeat(1001), '😀'.repeat(751)])('rechaza prompt inválido %j', value => {
  expect(validatePrompt(value)).not.toBe(true)
})
it.each(['a'.repeat(1000), '€'.repeat(1000), '😀'.repeat(750), '  texto\n ', '\ufeff'])('acepta límites Unicode y conserva texto', value => {
  expect(validatePrompt(value)).toBe(true)
  expect(textMetrics(value).points).toBe([...value].length)
})
it.each([null, {}, { ...success, extra: true }, { ...success, finalizacion: 'otra' }, { ...success, respuesta: '' }, { ...success, respuesta: '\udfff' }, { ...success, respuesta: 'x'.repeat(4097) }])('rechaza contratos de respuesta inválidos', async value => {
  const mutate = vi.fn().mockResolvedValue(value)
  await expect(createIAApi(mutate).consultar('ficticio', new AbortController().signal)).rejects.toMatchObject({ kind: 'contract' })
})
it.each(['ADMIN', 'USUARIO'])('permite a %s enviar solo prompt por transporte autenticado y muestra texto seguro', async rol => {
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, rol })),
    http.post('/api/v1/ia/consultas', async ({ request }) => {
      expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
      expect(await request.json()).toEqual({ prompt: '  ficticio\n ' })
      return HttpResponse.json({ respuesta: '<script>alert(1)</script>\nTexto', finalizacion: 'limite' })
    }))
  setup(); await enter(); send('  ficticio\n ')
  expect(await screen.findByText('<script>alert(1)</script> Texto')).toBeVisible()
  expect(document.querySelector('script')).toBeNull()
  expect(screen.getByText('Finalización: límite de generación alcanzado')).toBeVisible()
  expect(screen.getByLabelText('Consulta')).toHaveValue('')
  fireEvent.click(screen.getByText('Limpiar'))
  expect(screen.queryByRole('region', { name: 'Respuesta de IA' })).not.toBeInTheDocument()
})
it('protege IA sin sesión y no envía prompts inválidos', async () => {
  const provider = vi.fn(() => HttpResponse.json(success))
  server.use(http.post('/api/v1/ia/consultas', provider))
  setup()
  expect(await screen.findByRole('heading', { name: /Ingres/ })).toBeVisible()
  expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument()
  await enter(); send(' ')
  await screen.findByText('Escribí una consulta; no puede contener solo espacios.')
  expect(provider).not.toHaveBeenCalled()
})
it.each([
  [413, 'SOLICITUD_DEMASIADO_GRANDE', /solicitud es demasiado grande/],
  [422, 'PROMPT_INVALIDO', /servidor rechazó/],
  [403, 'PERMISO_DENEGADO', /No tenés acceso/],
  [429, 'IA_OCUPADA', /servicio de IA está ocupado/],
  [502, 'IA_RESPUESTA_INVALIDA', /respuesta inválida/],
  [503, 'IA_NO_DISPONIBLE', /Tu sesión sigue activa/],
  [504, 'IA_TIEMPO_AGOTADO', /agotó el tiempo/],
] as const)('maneja HTTP %s sin exponer mensajes upstream ni invalidar sesión', async (status, codigo, text) => {
  server.use(http.post('/api/v1/ia/consultas', () => HttpResponse.json({ error: { codigo, mensaje: 'CENTINELA_NO_MOSTRAR' } }, { status })))
  setup(); await enter(); send()
  expect(await screen.findByText(text)).toBeVisible()
  expect(screen.getByTestId('state')).toHaveTextContent('authenticated')
  expect(screen.queryByText(/CENTINELA_NO_MOSTRAR/)).not.toBeInTheDocument()
  if (status === 429) expect(screen.getByText(/servidor no indicó un tiempo/)).toBeVisible()
})
it('muestra solo el Retry-After real y no reintenta automáticamente', async () => {
  const handler = vi.fn(() => HttpResponse.json({ error: { codigo: 'IA_LIMITE_INTENTOS', mensaje: 'ficticio' } }, { status: 429, headers: { 'Retry-After': '30' } }))
  server.use(http.post('/api/v1/ia/consultas', handler))
  setup(); await enter(); send()
  expect(await screen.findByText('Podés reintentar en 30 segundos.')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Consulta'), { target: { value: 'otra' } })
  expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeDisabled()
  expect(handler).toHaveBeenCalledTimes(1)
})
it('maneja error de red sin cerrar sesión', async () => {
  server.use(http.post('/api/v1/ia/consultas', () => HttpResponse.error()))
  setup(); await enter(); send()
  expect(await screen.findByText(/No pudimos conectar/)).toBeVisible()
  expect(screen.getByTestId('state')).toHaveTextContent('authenticated')
})
it('401 utiliza la expiración existente de AuthProvider', async () => {
  server.use(http.post('/api/v1/ia/consultas', () => HttpResponse.json({ error: { codigo: 'AUTENTICACION_REQUERIDA', mensaje: 'ficticio' } }, { status: 401 })))
  setup(); await enter(); send()
  await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anonymous'))
  expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument()
})
it('403 de cambio obligatorio retira IA y usa el flujo restringido existente', async () => {
  setup(); await enter()
  server.use(http.post('/api/v1/ia/consultas', () => HttpResponse.json({ error: { codigo: 'CAMBIO_PASSWORD_REQUERIDO', mensaje: 'ficticio' } }, { status: 403 })),
    http.get('/api/v1/auth/me', () => HttpResponse.json({ id: testUser.id, debe_cambiar_password: true })))
  send()
  await screen.findByText('Debés cambiar tu contraseña inicial antes de acceder a la aplicación.')
  expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('Abrir IA'))
  expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument()
})
it('aborta una solicitud pendiente al desmontar y descarta su respuesta', async () => {
  let finish!: () => void
  let started!: () => void
  let signal!: AbortSignal
  const ready = new Promise<void>(resolve => { started = resolve })
  const block = new Promise<void>(resolve => { finish = resolve })
  server.use(http.post('/api/v1/ia/consultas', async ({ request }) => {
    signal = request.signal; started(); await block; return HttpResponse.json(success)
  }))
  setup(); await enter(); send(); await ready
  await screen.findByRole('button', { name: 'Cancelar consulta' })
  fireEvent.click(screen.getByText('Salir de IA'))
  await waitFor(() => expect(signal.aborted).toBe(true))
  await act(async () => { finish(); await block })
  fireEvent.click(screen.getByText('Abrir IA'))
  expect(await screen.findByLabelText('Consulta')).toHaveValue('')
  expect(screen.queryByText('Respuesta ficticia')).not.toBeInTheDocument()
})
it('el deadline local aborta sin reenvío automático ni pérdida de sesión', async () => {
  setup(); await enter()
  const original = globalThis.setTimeout
  let expire!: () => void
  vi.spyOn(globalThis, 'setTimeout').mockImplementation(((callback: TimerHandler, ms?: number, ...args: unknown[]) => {
    if (ms === 70000 && typeof callback === 'function') expire = () => callback()
    return original(callback, ms, ...args)
  }) as typeof setTimeout)
  let finish!: () => void
  const block = new Promise<void>(resolve => { finish = resolve })
  const handler = vi.fn(async () => { await block; return HttpResponse.json(success) })
  server.use(http.post('/api/v1/ia/consultas', handler))
  send()
  await waitFor(() => expect(handler).toHaveBeenCalledTimes(1))
  act(() => expire())
  expect(await screen.findByText(/Se agotó la espera local/)).toBeVisible()
  expect(screen.getByTestId('state')).toHaveTextContent('authenticated')
  await act(async () => { finish(); await block })
  expect(screen.queryByText('Respuesta ficticia')).not.toBeInTheDocument()
  expect(handler).toHaveBeenCalledTimes(1)
})
it('bloquea doble envío, cancela e ignora resultado tardío', async () => {
  let finish!: () => void
  let started!: () => void
  const ready = new Promise<void>(resolve => { started = resolve })
  const block = new Promise<void>(resolve => { finish = resolve })
  const handler = vi.fn(async () => { started(); await block; return HttpResponse.json(success) })
  server.use(http.post('/api/v1/ia/consultas', handler))
  setup(); await enter(); send(); await ready
  await screen.findByRole('button', { name: 'Cancelar consulta' })
  fireEvent.submit(screen.getByLabelText('Consulta').closest('form')!)
  expect(screen.getByRole('button', { name: 'Enviar consulta' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar consulta' }))
  await act(async () => { finish(); await block })
  expect(screen.getByText(/Consulta cancelada/)).toBeVisible()
  expect(screen.queryByText('Respuesta ficticia')).not.toBeInTheDocument()
  expect(handler).toHaveBeenCalledTimes(1)
})
it.each(['Salir de IA', 'Logout ficticio'])('limpia contenido y cancela al %s', async action => {
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  server.use(http.post('/api/v1/ia/consultas', () => HttpResponse.json(success)))
  setup(); await enter(); send()
  await screen.findByText('Respuesta ficticia')
  expect(screen.getByText('Finalización: completa')).toBeVisible()
  fireEvent.click(screen.getByText(action))
  await waitFor(() => expect(screen.queryByLabelText('Consulta')).not.toBeInTheDocument())
  expect(screen.queryByText('Respuesta ficticia')).not.toBeInTheDocument()
  expect(storage).not.toHaveBeenCalled()
  if (action === 'Salir de IA') {
    fireEvent.click(screen.getByText('Abrir IA'))
    expect(await screen.findByLabelText('Consulta')).toHaveValue('')
    expect(screen.queryByText('Respuesta ficticia')).not.toBeInTheDocument()
  }
})


it.each([
  ['RAG', 'Que es una API REST', 'RAG', 'SIN_EVIDENCIA'],
  ['AUTO', 'Que es una API REST', 'LLM_DIRECTO', 'GENERADA'],
  ['AUTO', 'Regularidad de unidad curricular', 'RAG', 'FUNDAMENTADA'],
] as const)('93G interfaz %s / %s', async (mode, question, strategy, status) => {
  const id = '11111111-1111-4111-8111-111111111111'
  const handler = vi.fn(async ({ request }: { request: Request }) => {
    expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
    expect(await request.json()).toEqual({ modo: mode, prompt: question, documento_id: id })
    return HttpResponse.json({ respuesta: status === 'SIN_EVIDENCIA' ? 'No hay evidencia pertinente.' : 'Respuesta verificable',
      estrategia: strategy, estado: status, finalizacion: status === 'SIN_EVIDENCIA' ? null : 'completa',
      fuentes: status === 'FUNDAMENTADA' ? [{ id: 'F1', pagina: 12 }] : [] })
  })
  server.use(http.get('/api/v1/ia/documentos', () => HttpResponse.json([{ id, titulo: 'Reglamento ficticio' }])),
    http.post('/api/v1/ia/respuestas', handler))
  setup(); await enter()
  fireEvent.change(screen.getByLabelText('Estrategia'), { target: { value: mode } })
  await screen.findByRole('option', { name: 'Reglamento ficticio' })
  send(question)
  await screen.findByText(`Estado: ${status}`)
  expect(screen.getByText(`Estrategia: ${strategy}`)).toBeVisible()
  expect(handler).toHaveBeenCalledTimes(1)
  if (status !== 'FUNDAMENTADA') expect(screen.queryByText(/PDF 12/)).not.toBeInTheDocument()
  else expect(screen.getByText(/PDF 12/)).toBeVisible()
})

it('AUTO rechaza contratos inconsistentes en lugar de abstenerse', async () => {
  const mutate = vi.fn().mockResolvedValue({ respuesta: 'Texto', estrategia: 'LLM_DIRECTO', estado: 'SIN_EVIDENCIA',
    finalizacion: null, fuentes: [] })
  await expect(createIAApi(mutate).auto('Pregunta', '', new AbortController().signal)).rejects.toMatchObject({ kind: 'contract' })
})

it('RAG mantiene un error real 502 visible y no muestra SIN_EVIDENCIA', async () => {
  const id = '11111111-1111-4111-8111-111111111111'
  server.use(http.get('/api/v1/ia/documentos', () => HttpResponse.json([{ id, titulo: 'Reglamento ficticio' }])),
    http.post('/api/v1/ia/respuestas', () => HttpResponse.json({ error: { codigo: 'IA_RESPUESTA_INVALIDA', mensaje: 'PRIVADO' } }, { status: 502 })))
  setup(); await enter()
  fireEvent.change(screen.getByLabelText('Estrategia'), { target: { value: 'RAG' } })
  await screen.findByRole('option', { name: 'Reglamento ficticio' })
  send('Regularidad')
  await screen.findByText(/El servicio de IA/)
  expect(screen.queryByText('Estado: SIN_EVIDENCIA')).not.toBeInTheDocument()
  expect(screen.queryByText('PRIVADO')).not.toBeInTheDocument()
})
