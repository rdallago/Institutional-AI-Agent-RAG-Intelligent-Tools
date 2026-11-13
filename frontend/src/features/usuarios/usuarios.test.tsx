import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { AppProviders } from '../../app/providers'
import { AppRoutes } from '../../router/routes'
import { useAuth } from '../auth/model/authContext'
import { server } from '../../test/mocks/server'
import { testToken, testUser } from '../../test/mocks/handlers'
import { parseConsulta } from './api/usuariosApi'

const profile = { ...testUser, id: '00000000-0000-0000-0000-000000000001', nombre: 'Bruno', apellido: 'Consulta', email: 'bruno@example.com', rol: 'USUARIO' }
const other = { ...profile, id: '00000000-0000-0000-0000-000000000002', nombre: 'Carla', email: 'carla@example.com', activo: false }

function Controls({ path }: { path: string }) {
  const { login, state } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  return <div>
    <output data-testid="auth-status">{state.status}</output>
    <output data-testid="url">{location.pathname}{location.search}</output>
    <button onClick={() => { void login({ email: 'ana@example.com', password: 'ficticia para pruebas' }).catch(() => {}) }}>Acceder de prueba</button>
    <button onClick={() => navigate(path)}>Abrir consulta</button>
    <button onClick={() => navigate(`/usuarios/${other.id}`)}>Abrir segundo detalle</button>
    <button onClick={() => navigate('/dashboard')}>Ir al inicio</button>
  </div>
}
function setup(path = '/usuarios') {
  return render(<AppProviders><MemoryRouter><Controls path={path} /><AppRoutes /></MemoryRouter></AppProviders>)
}
async function enter() {
  fireEvent.click(screen.getByText('Acceder de prueba'))
  await screen.findByRole('heading', { name: 'Bienvenido, Ana' }, { timeout: 5000 })
  fireEvent.click(screen.getByText('Abrir consulta'))
}
async function select(label: string, option: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole('combobox', { name: label }))
  await user.click(await screen.findByRole('option', { name: option }))
}
const displayed = async (text: string) => {
  await waitFor(() => expect(screen.getAllByText(text).some(el => !!el && getComputedStyle(el.closest('article') ?? el).display !== 'none')).toBe(true))
}

it('ADMIN consulta listado con Bearer, campos reales y parámetros predeterminados', async () => {
  const calls: string[] = []
  server.use(http.get('/api/v1/usuarios', ({ request }) => {
    expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
    calls.push(new URL(request.url).search)
    return HttpResponse.json([profile])
  }))
  setup()
  await enter()
  await displayed('bruno@example.com')
  expect(calls).toEqual(['?estado=activos&limite=20&desplazamiento=0'])
  expect(screen.getAllByText('Bruno').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Consulta').length).toBeGreaterThan(0)
  expect(screen.getAllByText('USUARIO').length).toBeGreaterThan(0)
  expect(screen.getAllByText('Activo').length).toBeGreaterThan(0)
  expect(screen.queryByRole('button', { name: /Crear|Modificar|Eliminar|Reactivar|Asignar/ })).not.toBeInTheDocument()
})

it('filtra con valores exactos y reinicia offset al cambiar estado o límite', async () => {
  const calls: string[] = []
  server.use(http.get('/api/v1/usuarios', ({ request }) => { calls.push(new URL(request.url).search); return HttpResponse.json([other]) }))
  setup('/usuarios?estado=todos&limite=10&desplazamiento=20')
  await enter()
  await displayed('carla@example.com')
  await select('Estado', 'Inactivos')
  await waitFor(() => expect(calls).toContain('?estado=inactivos&limite=10&desplazamiento=0'))
  await select('Estado', 'Activos')
  await waitFor(() => expect(calls).toContain('?estado=activos&limite=10&desplazamiento=0'))
  await select('Perfiles por página', '50')
  await waitFor(() => expect(calls).toContain('?estado=activos&limite=50&desplazamiento=0'))
  expect(screen.getByTestId('url')).toHaveTextContent('estado=activos&limite=50&desplazamiento=0')
})

it('pagina sin total y permite volver desde una página vacía', async () => {
  server.use(http.get('/api/v1/usuarios', ({ request }) => HttpResponse.json(new URL(request.url).searchParams.get('desplazamiento') === '0' ? [profile] : [])))
  setup('/usuarios?limite=1')
  await enter()
  await displayed('bruno@example.com')
  expect(screen.getByRole('button', { name: 'Anterior' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
  expect(await screen.findByText(/No hay perfiles en esta página/)).toBeVisible()
  expect(screen.getByText('Página sin resultados')).toBeVisible()
  expect(screen.getByTestId('url')).toHaveTextContent('desplazamiento=1')
  expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled()
  expect(screen.queryByText(/de \d+ registros|total de registros/i)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Anterior' }))
  await displayed('bruno@example.com')
})

it('lista vacía sin ofrecer siguiente ni inventar perfiles', async () => {
  setup()
  await enter()
  expect(await screen.findByText(/No hay perfiles en esta página/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled()
})

it('detalle inactivo por UUID y retorno conservando filtro, tamaño y offset', async () => {
  server.use(http.get('/api/v1/usuarios', () => HttpResponse.json([other])),
    http.get('/api/v1/usuarios/:id', ({ params }) => { expect(params.id).toBe(other.id); return HttpResponse.json(other) }))
  setup('/usuarios?estado=inactivos&limite=10&desplazamiento=30')
  await enter()
  await displayed('carla@example.com')
  // Cards and table coexist for responsive rendering; choose the visible card link.
  const card = screen.getByRole('article')
  fireEvent.click(within(card).getByRole('link', { name: 'Ver perfil de Carla Consulta' }))
  expect(await screen.findByRole('heading', { name: 'Detalle de perfil' }, { timeout: 5000 })).toBeVisible()
  expect(await screen.findByText(other.id)).toBeVisible()
  expect(screen.getByText('Inactivo')).toBeVisible()
  expect(screen.getByText('carla@example.com')).toBeVisible()
  fireEvent.click(screen.getByRole('link', { name: 'Volver al listado' }))
  await displayed('carla@example.com')
  expect(screen.getByTestId('url')).toHaveTextContent('/usuarios?estado=inactivos&limite=10&desplazamiento=30')
})

it.each([403, 422, 500])('error %s saneado y reintento manual de listado', async status => {
  server.use(http.get('/api/v1/usuarios', () => HttpResponse.json({ error: { mensaje: 'private-email@example.com', usuario_id: profile.id } }, { status })))
  setup()
  await enter()
  expect(await screen.findByRole('button', { name: 'Reintentar consulta' })).toBeVisible()
  expect(screen.queryByText('private-email@example.com')).not.toBeInTheDocument()
  expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated')
  server.use(http.get('/api/v1/usuarios', () => HttpResponse.json([profile])))
  fireEvent.click(screen.getByRole('button', { name: 'Reintentar consulta' }))
  await displayed('bruno@example.com')
})

it.each(['network', 'contract'])('error de %s no conserva datos previos ni cierra sesión', async scenario => {
  server.use(http.get('/api/v1/usuarios', () => scenario === 'network' ? HttpResponse.error() : HttpResponse.json({ users: [profile] })))
  setup()
  await enter()
  expect(await screen.findByRole('button', { name: 'Reintentar consulta' })).toBeVisible()
  expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated')
  expect(screen.queryByText('bruno@example.com')).not.toBeInTheDocument()
})

it('401 protegido borra sesión y perfiles y vuelve a login', async () => {
  server.use(http.get('/api/v1/usuarios', () => HttpResponse.json({ error: { codigo: 'AUTENTICACION_REQUERIDA' } }, { status: 401 })))
  setup()
  await enter()
  expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
  expect(screen.queryByText('bruno@example.com')).not.toBeInTheDocument()
  expect(screen.getByTestId('auth-status')).toHaveTextContent('anonymous')
})

it.each([404, 403, 500])('detalle maneja HTTP %s sin reflejar datos sensibles', async status => {
  server.use(http.get('/api/v1/usuarios/:id', () => HttpResponse.json({ error: { mensaje: 'sensitive-profile' } }, { status })))
  setup(`/usuarios/${profile.id}`)
  await enter()
  expect(await screen.findByRole('button', { name: 'Reintentar consulta' })).toBeVisible()
  expect(screen.queryByText('sensitive-profile')).not.toBeInTheDocument()
})

it('USUARIO no puede enviar consultas administrativas aunque escriba la ruta', async () => {
  const list = vi.fn(() => HttpResponse.json([profile]))
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, rol: 'USUARIO' })), http.get('/api/v1/usuarios', list))
  setup()
  await enter()
  expect(await screen.findByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
  expect(list).not.toHaveBeenCalled()
  expect(screen.queryByRole('link', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
})

it('cambiar filtro cancela la petición vieja e ignora su respuesta tardía', async () => {
  let release!: () => void
  let started = false
  let aborted = false
  const gate = new Promise<void>(resolve => { release = resolve })
  server.use(http.get('/api/v1/usuarios', async ({ request }) => {
    if (new URL(request.url).searchParams.get('estado') === 'activos') {
      started = true
      request.signal.addEventListener('abort', () => { aborted = true })
      await gate
      return HttpResponse.json([profile])
    }
    return HttpResponse.json([other])
  }))
  setup()
  await enter()
  await waitFor(() => expect(started).toBe(true))
  expect(screen.getByText('Cargando perfiles…')).toBeVisible()
  await select('Estado', 'Inactivos')
  await displayed('carla@example.com')
  await act(async () => { release(); await gate })
  expect(aborted).toBe(true)
  expect(screen.queryByText('bruno@example.com')).not.toBeInTheDocument()
})

it('cambiar UUID no permite que el detalle anterior sobrescriba al nuevo', async () => {
  let release!: () => void
  let started = false
  const gate = new Promise<void>(resolve => { release = resolve })
  server.use(http.get('/api/v1/usuarios/:id', async ({ params }) => {
    if (params.id === profile.id) { started = true; await gate; return HttpResponse.json(profile) }
    return HttpResponse.json(other)
  }))
  setup(`/usuarios/${profile.id}`)
  await enter()
  await waitFor(() => expect(started).toBe(true))
  fireEvent.click(screen.getByText('Abrir segundo detalle'))
  expect(await screen.findByText('carla@example.com')).toBeVisible()
  await act(async () => { release(); await gate })
  expect(screen.queryByText('bruno@example.com')).not.toBeInTheDocument()
})

it('logout cancela listado pendiente y una sesión nueva no recibe sus datos', async () => {
  let release!: () => void
  let started = false
  let aborted = false
  const gate = new Promise<void>(resolve => { release = resolve })
  server.use(http.get('/api/v1/usuarios', async ({ request }) => {
    started = true
    request.signal.addEventListener('abort', () => { aborted = true })
    await gate
    return HttpResponse.json([profile])
  }))
  setup()
  await enter()
  await waitFor(() => expect(started).toBe(true))
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
  await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  server.use(http.get('/api/v1/usuarios', () => HttpResponse.json([other])))
  await enter()
  await displayed('carla@example.com')
  await act(async () => { release(); await gate })
  expect(aborted).toBe(true)
  expect(screen.queryByText('bruno@example.com')).not.toBeInTheDocument()
})

it('abandono de la pantalla cancela su consulta', async () => {
  let release!: () => void
  let started = false
  let aborted = false
  const gate = new Promise<void>(resolve => { release = resolve })
  server.use(http.get('/api/v1/usuarios', async ({ request }) => {
    started = true
    request.signal.addEventListener('abort', () => { aborted = true })
    await gate
    return HttpResponse.json([profile])
  }))
  setup()
  await enter()
  await waitFor(() => expect(started).toBe(true))
  fireEvent.click(screen.getByText('Ir al inicio'))
  await screen.findByRole('heading', { name: 'Bienvenido, Ana' })
  await act(async () => { release(); await gate })
  expect(aborted).toBe(true)
  expect(screen.queryByText('bruno@example.com')).not.toBeInTheDocument()
})

it.each(['limite=0&desplazamiento=-1', 'limite=101&estado=otro', 'limite=abc&desplazamiento=Infinity', 'limite=1.5&desplazamiento=2.5'])(
  'normaliza parámetros inválidos sin enviar valores fuera del contrato: %s', search => {
    expect(parseConsulta(new URLSearchParams(search))).toEqual({ estado: 'activos', limite: 20, desplazamiento: 0 })
  })

it('respeta límite 100 y offset válido sin inventar total', () => {
  expect(parseConsulta(new URLSearchParams('estado=todos&limite=100&desplazamiento=200'))).toEqual({ estado: 'todos', limite: 100, desplazamiento: 200 })
})
