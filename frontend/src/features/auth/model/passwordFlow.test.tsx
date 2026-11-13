import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import { AppProviders } from '../../../app/providers'
import { AppRoutes } from '../../../router/routes'
import { useAuth } from './authContext'
import { server } from '../../../test/mocks/server'
import { testToken, testUser } from '../../../test/mocks/handlers'

const OLD = 'contraseña actual ficticia'
const NEW = 'contraseña definitiva ficticia'
const minimal = { id: testUser.id, debe_cambiar_password: true }
const normal = { ...testUser, debe_cambiar_password: false }
function Controls() {
  const { login, state, get } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  return <div>
    <output data-testid="status">{state.status}</output><output data-testid="path">{location.pathname}</output>
    <button onClick={() => { void login({ email: 'ana@example.com', password: OLD }).catch(() => {}) }}>Acceso ficticio</button>
    <button onClick={() => { void get('/usuarios', new AbortController().signal).catch(() => {}) }}>Consulta de prueba</button>
    {['/dashboard', '/usuarios', '/usuarios/nuevo', '/usuarios/id/editar', '/mi-perfil', '/login', '/unknown', '/cambiar-password'].map(path =>
      <button key={path} onClick={() => navigate(path)}>Ir {path}</button>)}
  </div>
}
function setup(pending = true, path = '/login') {
  server.use(http.post('/api/v1/auth/login', () => HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: pending })),
    http.get('/api/v1/auth/me', () => HttpResponse.json(pending ? minimal : normal)))
  return render(<AppProviders><MemoryRouter initialEntries={[path]}><Controls /><AppRoutes /></MemoryRouter></AppProviders>)
}
async function enter(pending = true) {
  fireEvent.click(screen.getByText('Acceso ficticio'))
  if (pending) await screen.findByText('Debés cambiar tu contraseña inicial antes de acceder a la aplicación.')
  else await screen.findByRole('heading', { name: 'Bienvenido, Ana' })
}
function fill(confirmation = NEW) {
  fireEvent.change(screen.getByLabelText('Contraseña actual'), { target: { value: OLD } })
  fireEvent.change(screen.getByLabelText('Contraseña nueva'), { target: { value: NEW } })
  fireEvent.change(screen.getByLabelText('Confirmar contraseña nueva'), { target: { value: confirmation } })
}
async function submit() {
  await waitFor(() => expect(screen.getByRole('button', { name: 'Guardar nueva contraseña' })).toBeEnabled())
  fireEvent.click(screen.getByRole('button', { name: 'Guardar nueva contraseña' }))
}

it.each(['/dashboard', '/usuarios', '/usuarios/nuevo', '/usuarios/id/editar', '/mi-perfil', '/login', '/unknown'])(
  'sesión restringida usa me mínimo y bloquea %s sin layout normal ni consultas', async path => {
    const users = vi.fn(() => HttpResponse.json([]))
    server.use(http.get('/api/v1/usuarios', users))
    setup(); await enter()
    fireEvent.click(screen.getByText('Ir ' + path))
    expect(screen.getByTestId('path')).toHaveTextContent('/cambiar-password')
    expect(screen.getByTestId('status')).toHaveTextContent('passwordChangeRequired')
    expect(screen.queryByRole('link', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
    expect(screen.queryByText('Ana Pruebas')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Consulta de prueba'))
    await act(async () => {})
    expect(users).not.toHaveBeenCalled()
  })

it.each([false, true])('cambio voluntario/obligatorio %s limpia secretos y exige login tras 204', async pending => {
  let input: unknown
  const logout = vi.fn(() => new HttpResponse(null, { status: 204 }))
  const password = vi.fn(async ({ request }: { request: Request }) => {
    expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
    input = await request.json()
    return new HttpResponse(null, { status: 204 })
  })
  server.use(http.put('/api/v1/auth/password', password), http.post('/api/v1/auth/logout', logout))
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  const cookie = vi.spyOn(Document.prototype, 'cookie', 'set')
  setup(pending); await enter(pending)
  if (!pending) fireEvent.click(screen.getByRole('link', { name: 'Cambiar contraseña' }))
  await screen.findByLabelText('Contraseña actual')
  fill(); await submit()
  expect(await screen.findByText('Contraseña cambiada. Ingresá nuevamente con tu nueva contraseña.')).toBeVisible()
  expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
  expect(screen.getByLabelText('Contraseña')).toHaveValue('')
  expect(screen.queryByLabelText('Contraseña nueva')).not.toBeInTheDocument()
  expect(input).toEqual({ password_actual: OLD, password_nueva: NEW })
  expect(password).toHaveBeenCalledTimes(1)
  expect(logout).not.toHaveBeenCalled()
  expect(storage).not.toHaveBeenCalled(); expect(cookie).not.toHaveBeenCalled()
  fireEvent.click(screen.getByText('Consulta de prueba'))
  expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
})

it('confirmación y política visual impiden envío y permiten mostrar cada secreto', async () => {
  const password = vi.fn()
  server.use(http.put('/api/v1/auth/password', password))
  setup(); await enter()
  expect(screen.getByText(/El servidor también verifica contraseñas comunes/)).toBeVisible()
  fill('no coincide')
  expect(screen.getByRole('button', { name: 'Guardar nueva contraseña' })).toBeDisabled()
  fireEvent.submit(screen.getByLabelText('Contraseña actual').closest('form')!)
  expect(await screen.findByText('Las contraseñas deben coincidir exactamente.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Mostrar contraseña nueva' }))
  expect(screen.getByLabelText('Contraseña nueva')).toHaveAttribute('type', 'text')
  fireEvent.click(screen.getByRole('button', { name: 'Ocultar contraseña nueva' }))
  expect(screen.getByLabelText('Contraseña nueva')).toHaveAttribute('type', 'password')
  expect(password).not.toHaveBeenCalled()
})

it.each([['CREDENCIALES_INVALIDAS', 401, 'La contraseña actual es incorrecta.'],
  ['PASSWORD_INVALIDA', 422, 'El servidor rechazó la nueva contraseña. Revisá la política y elegí otra.'],
  ['PASSWORD_REUTILIZADA', 422, 'Elegí una contraseña diferente de la actual y de la inicial.']] as const)(
  '%s mantiene la sesión válida y nunca reproduce mensajes sensibles', async (code, status, message) => {
    server.use(http.put('/api/v1/auth/password', () => HttpResponse.json({ error: { codigo: code, mensaje: OLD } }, { status })))
    setup(); await enter(); fill(); await submit()
    expect(await screen.findByText(message)).toBeVisible()
    expect(screen.getByTestId('status')).toHaveTextContent('passwordChangeRequired')
    expect(screen.getByLabelText('Contraseña actual')).toHaveValue('')
    expect(screen.getByLabelText('Contraseña nueva')).toHaveValue('')
    expect(screen.queryByText(OLD)).not.toBeInTheDocument()
  })

it('429 respeta Retry-After y no reintenta automáticamente', async () => {
  const password = vi.fn(() => HttpResponse.json({ error: { codigo: 'LIMITE_INTENTOS' } }, { status: 429, headers: { 'Retry-After': '2' } }))
  server.use(http.put('/api/v1/auth/password', password))
  setup(); await enter(); fill(); await submit()
  expect(await screen.findByText('Podés volver a intentar en 2 segundos.')).toBeVisible()
  fill()
  expect(screen.getByRole('button', { name: 'Guardar nueva contraseña' })).toBeDisabled()
  await waitFor(() => expect(screen.queryByText(/Podés volver a intentar/)).not.toBeInTheDocument(), { timeout: 4000 })
  expect(password).toHaveBeenCalledTimes(1)
  await submit()
  await waitFor(() => expect(password).toHaveBeenCalledTimes(2))
})

it.each(['network', '500', 'contract'])('resultado %s ambiguo limpia todo sin reenviar', async scenario => {
  const password = vi.fn(() => scenario === 'network' ? HttpResponse.error()
    : HttpResponse.json({ mensaje: OLD }, { status: scenario === '500' ? 500 : 200 }))
  server.use(http.put('/api/v1/auth/password', password))
  setup(); await enter(); fill(); await submit()
  expect(await screen.findByText(/No pudimos confirmar el cambio/)).toBeVisible()
  expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
  expect(screen.queryByLabelText('Contraseña actual')).not.toBeInTheDocument()
  expect(screen.queryByText(OLD)).not.toBeInTheDocument()
  expect(password).toHaveBeenCalledTimes(1)
})

it('401 de sesión inválida es terminal también en password', async () => {
  server.use(http.put('/api/v1/auth/password', () => HttpResponse.json({ error: { codigo: 'AUTENTICACION_REQUERIDA' } }, { status: 401 })))
  setup(); await enter(); fill(); await submit()
  expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
  expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
})

it('ADMIN normal que pasa a pendiente pierde identidad, navegación y datos privados', async () => {
  setup(false); await enter(false)
  expect(screen.getByRole('link', { name: 'Administración de usuarios' })).toBeVisible()
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json(minimal)))
  fireEvent(window, new Event('focus'))
  await screen.findByText('Debés cambiar tu contraseña inicial antes de acceder a la aplicación.')
  expect(screen.queryByText('Ana Pruebas')).not.toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
})

it('403 CAMBIO_PASSWORD_REQUERIDO revalida me y retira administración', async () => {
  setup(false); await enter(false)
  server.use(http.get('/api/v1/usuarios', () => HttpResponse.json({ error: { codigo: 'CAMBIO_PASSWORD_REQUERIDO' } }, { status: 403 })),
    http.get('/api/v1/auth/me', () => HttpResponse.json(minimal)))
  fireEvent.click(screen.getByText('Ir /usuarios'))
  await screen.findByText('Debés cambiar tu contraseña inicial antes de acceder a la aplicación.')
  expect(screen.getByTestId('path')).toHaveTextContent('/cambiar-password')
  expect(screen.queryByRole('heading', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
})

it.each([{ id: testUser.id }, { ...minimal, rol: 'ADMIN' }, { ...minimal, debe_cambiar_password: 'true' }])(
  'me mal formado no autoriza una sesión: %#', async context => {
    setup()
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json(context)))
    fireEvent.click(screen.getByText('Acceso ficticio'))
    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
    expect(screen.queryByRole('heading', { name: 'Cambiar contraseña' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
  })

it('un token emitido como restringido nunca se promueve por un me contradictorio', async () => {
  setup()
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json(normal)))
  fireEvent.click(screen.getByText('Acceso ficticio'))
  await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
  expect(screen.queryByText('Bienvenido, Ana')).not.toBeInTheDocument()
})

it('logout y recarga no conservan el token restringido', async () => {
  const view = setup(); await enter()
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
  await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  view.unmount()
  setup(true, '/cambiar-password')
  expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
})

it('la expiración retira también la sesión restringida', async () => {
  const timers = vi.spyOn(globalThis, 'setTimeout')
  setup(); await enter()
  const timer = timers.mock.calls.find(([, delay]) => typeof delay === 'number' && delay > 890000 && delay <= 900000)
  expect(timer).toBeDefined()
  act(() => { (timer![0] as () => void)() })
  await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
})

it('una respuesta tardía de password no cierra otra sesión', async () => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const password = vi.fn(async () => { await gate; return new HttpResponse(null, { status: 204 }) })
  server.use(http.put('/api/v1/auth/password', password))
  setup(); await enter(); fill(); await submit()
  await waitFor(() => expect(password).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
  await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  server.use(http.post('/api/v1/auth/login', () => HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false })),
    http.get('/api/v1/auth/me', () => HttpResponse.json({ ...normal, nombre: 'Nueva' })))
  fireEvent.click(screen.getByText('Acceso ficticio'))
  await screen.findByRole('heading', { name: 'Bienvenido, Nueva' })
  await act(async () => { release(); await gate })
  expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
  expect(screen.getByRole('heading', { name: 'Bienvenido, Nueva' })).toBeVisible()
})

it('contraseña actual incorrecta conserva también una sesión normal', async () => {
  server.use(http.put('/api/v1/auth/password', () => HttpResponse.json({ error: { codigo: 'CREDENCIALES_INVALIDAS' } }, { status: 401 })))
  setup(false); await enter(false)
  fireEvent.click(screen.getByRole('link', { name: 'Cambiar contraseña' }))
  await screen.findByLabelText('Contraseña actual'); fill(); await submit()
  expect(await screen.findByText('La contraseña actual es incorrecta.')).toBeVisible()
  expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
  expect(screen.getByRole('link', { name: 'Mi perfil' })).toBeVisible()
})

it.each(['timeout', 'expiry'])('%s durante el cambio descarta sesión e informa resultado ambiguo', async reason => {
  const timers = vi.spyOn(globalThis, 'setTimeout')
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const password = vi.fn(async () => { await gate; return new HttpResponse(null, { status: 204 }) })
  server.use(http.put('/api/v1/auth/password', password))
  setup(); await enter(); fill(); await submit()
  await waitFor(() => expect(password).toHaveBeenCalledTimes(1))
  const timer = timers.mock.calls.find(([, delay]) => reason === 'timeout' ? delay === 15000 : typeof delay === 'number' && delay > 890000 && delay <= 900000)
  expect(timer).toBeDefined()
  await act(async () => { (timer![0] as () => void)() })
  expect(await screen.findByText(reason === 'timeout' ? /No pudimos confirmar el cambio/ : /La sesión terminó durante el cambio/)).toBeVisible()
  expect(screen.getByTestId('status')).toHaveTextContent('anonymous')
  expect(screen.queryByLabelText('Contraseña nueva')).not.toBeInTheDocument()
  await act(async () => { release(); await gate })
  expect(password).toHaveBeenCalledTimes(1)
})
