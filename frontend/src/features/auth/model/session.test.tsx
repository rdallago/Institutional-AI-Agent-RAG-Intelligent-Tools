import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { AppProviders } from '../../../app/providers'
import { AppRoutes } from '../../../router/routes'
import { useAuth } from './authContext'
import { server } from '../../../test/mocks/server'
import { testToken, testUser } from '../../../test/mocks/handlers'

function Controls() {
  const { login, state } = useAuth()
  const navigate = useNavigate()
  return <div>
    <output data-testid="session-status">{state.status}</output>
    <button onClick={() => { void login({ email: 'ana@example.com', password: 'ficticia de pruebas' }).catch(() => {}) }}>Acceso ficticio</button>
    {['/dashboard', '/mi-perfil', '/usuarios', '/usuarios/nuevo', '/usuarios/id', '/usuarios/id/editar', '/cambiar-password'].map(path =>
      <button key={path} onClick={() => navigate(path)}>Ir {path}</button>)}
  </div>
}

function setup(path = '/login') {
  return render(<AppProviders><MemoryRouter initialEntries={[path]}><Controls /><AppRoutes /></MemoryRouter></AppProviders>)
}

async function enter() {
  fireEvent.click(screen.getByText('Acceso ficticio'))
  await screen.findByRole('heading', { name: 'Bienvenido, Ana' })
}

afterEach(() => { vi.useRealTimers() })

describe('rutas y presentación por rol', () => {
  it.each(['/dashboard', '/mi-perfil', '/usuarios', '/usuarios/nuevo', '/usuarios/id', '/usuarios/id/editar', '/cambiar-password'])(
    'redirige acceso anónimo desde %s a login', async path => {
      setup(path)
      expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
      expect(screen.queryByRole('button', { name: 'Cerrar sesión' })).not.toBeInTheDocument()
    })

  it('ADMIN navega a perfil real y secciones reservadas sin operaciones', async () => {
    setup()
    await enter()
    expect(screen.getByRole('link', { name: 'Administración de usuarios' })).toBeVisible()
    fireEvent.click(screen.getByRole('link', { name: 'Mi perfil' }))
    expect(await screen.findByRole('heading', { name: 'Mi perfil' }, { timeout: 5000 })).toBeVisible()
    expect(screen.getByText('Activo')).toBeVisible()
    expect(screen.getByText('Fecha de creación')).toBeVisible()
    expect(screen.getByText('ana@example.com')).toBeVisible()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Ir /usuarios'))
    expect(await screen.findByRole('heading', { name: 'Administración de usuarios' }, { timeout: 5000 })).toBeVisible()
    fireEvent.click(screen.getByText('Ir /usuarios/id'))
    expect(await screen.findByText('El perfil no está disponible.')).toBeVisible()
    fireEvent.click(screen.getByText('Ir /usuarios/nuevo'))
    expect(await screen.findByRole('heading', { name: 'Crear perfil' }, { timeout: 5000 })).toBeVisible()
    expect(screen.queryByLabelText('Contraseña')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Ir /usuarios/id/editar'))
    expect(await screen.findByText('El perfil no está disponible.')).toBeVisible()
    fireEvent.click(screen.getByText('Ir /cambiar-password'))
    expect(await screen.findByRole('heading', { name: 'Cambiar contraseña' })).toBeVisible()
  })

  it.each(['/usuarios', '/usuarios/nuevo', '/usuarios/id', '/usuarios/id/editar'])(
    'USUARIO no ve navegación administrativa ni puede abrir %s', async path => {
      server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, rol: 'USUARIO' })))
      setup()
      await enter()
      expect(screen.queryByRole('link', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
      fireEvent.click(screen.getByText('Ir ' + path))
      expect(await screen.findByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
      expect(screen.queryByText(/Sección reservada/)).not.toBeInTheDocument()
    })

  it('actualiza identidad y rol desde me sin una segunda copia de perfil', async () => {
    setup()
    await enter()
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, nombre: 'Beatriz', rol: 'USUARIO' })))
    fireEvent(window, new Event('focus'))
    expect(await screen.findByRole('heading', { name: 'Bienvenido, Beatriz' })).toBeVisible()
    expect(screen.queryByRole('link', { name: 'Administración de usuarios' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: 'Mi perfil' }))
    expect(await screen.findByText('Beatriz')).toBeVisible()
  })

  it('democión mientras se visita administración retira acceso inmediatamente', async () => {
    setup()
    await enter()
    fireEvent.click(screen.getByText('Ir /usuarios'))
    expect(await screen.findByRole('heading', { name: 'Administración de usuarios' }, { timeout: 5000 })).toBeVisible()
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, rol: 'USUARIO' })))
    fireEvent(window, new Event('focus'))
    expect(await screen.findByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
  })
})

describe('logout y aislamiento de sesiones', () => {
  it('envía token capturado, limpia datos y confirma revocación solo tras 204', async () => {
    const logout = vi.fn(({ request }: { request: Request }) => {
      expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
      return new HttpResponse(null, { status: 204 })
    })
    server.use(http.post('/api/v1/auth/logout', logout))
    setup()
    await enter()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
    expect(screen.getByText(/El servidor confirmó la revocación/)).toBeVisible()
    expect(screen.queryByText('ana@example.com')).not.toBeInTheDocument()
    expect(logout).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByText('Ir /mi-perfil'))
    expect(screen.getByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
  })

  it.each(['network', '500', '401'])('limpia igualmente ante logout %s y comunica el resultado real', async scenario => {
    server.use(http.post('/api/v1/auth/logout', () => scenario === 'network' ? HttpResponse.error()
      : new HttpResponse(null, { status: Number(scenario) })))
    setup()
    await enter()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    expect(screen.getByText(scenario === '401' ? /ya no acepta ese token/ : /No se pudo confirmar la revocación remota/)).toBeVisible()
    expect(screen.queryByText('ana@example.com')).not.toBeInTheDocument()
  })

  it('bloquea operaciones y doble logout mientras espera revocación', async () => {
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    const logout = vi.fn(async () => { await gate; return new HttpResponse(null, { status: 204 }) })
    const login = vi.fn(() => HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false }))
    server.use(http.post('/api/v1/auth/logout', logout), http.post('/api/v1/auth/login', login))
    setup()
    await enter()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    expect(await screen.findByText('Cerrando sesión…')).toBeVisible()
    expect(screen.queryByText('ana@example.com')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Acceso ficticio'))
    await waitFor(() => expect(logout).toHaveBeenCalledTimes(1))
    expect(login).toHaveBeenCalledTimes(1)
    release()
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  })

  it('una respuesta inesperada de logout no se anuncia como revocación confirmada', async () => {
    server.use(http.post('/api/v1/auth/logout', () => HttpResponse.json({ unexpected: true })))
    setup()
    await enter()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    expect(screen.getByText(/No se pudo confirmar la revocación remota/)).toBeVisible()
  })

  it('logout con servidor que no responde termina por timeout y borra la sesión', async () => {
    let release!: () => void
    let started = false
    const gate = new Promise<void>(resolve => { release = resolve })
    server.use(http.post('/api/v1/auth/logout', async () => {
      started = true
      await gate
      return new HttpResponse(null, { status: 204 })
    }))
    setup()
    await enter()
    const timers = vi.spyOn(globalThis, 'setTimeout')
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    await waitFor(() => expect(started).toBe(true))
    const timeout = timers.mock.calls.find(([, delay]) => delay === 5000)
    expect(timeout).toBeDefined()
    act(() => { (timeout![0] as () => void)() })
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    expect(screen.getByText(/No se pudo confirmar la revocación remota/)).toBeVisible()
    await act(async () => { release(); await gate })
    expect(screen.getByTestId('session-status')).toHaveTextContent('anonymous')
  })

  it('una respuesta me anterior al logout no restaura datos de la sesión previa', async () => {
    setup()
    await enter()
    let release!: () => void
    let started = false
    const gate = new Promise<void>(resolve => { release = resolve })
    server.use(http.get('/api/v1/auth/me', async () => { started = true; await gate; return HttpResponse.json({ ...testUser, nombre: 'Anterior' }) }))
    fireEvent(window, new Event('focus'))
    await waitFor(() => expect(started).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, nombre: 'Nueva' })))
    fireEvent.click(screen.getByText('Acceso ficticio'))
    await screen.findByRole('heading', { name: 'Bienvenido, Nueva' })
    await act(async () => { release(); await gate })
    expect(screen.getByRole('heading', { name: 'Bienvenido, Nueva' })).toBeVisible()
    expect(screen.queryByText(/Anterior/)).not.toBeInTheDocument()
  })

  it('recarga pierde identidad; logout no escribe almacenamiento persistente', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    const cookie = vi.spyOn(Document.prototype, 'cookie', 'set')
    const view = setup()
    await enter()
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    await enter()
    view.unmount()
    setup('/mi-perfil')
    expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
    expect(storage).not.toHaveBeenCalled()
    expect(cookie).not.toHaveBeenCalled()
  })
})

describe('expiración y errores de sesión', () => {
  it('programa 15 minutos desde el inicio del login y expira cancelando identidad', async () => {
    const timers = vi.spyOn(globalThis, 'setTimeout')
    setup()
    await enter()
    const expiry = timers.mock.calls.find(([, delay]) => typeof delay === 'number' && delay > 890000 && delay <= 900000)
    expect(expiry).toBeDefined()
    act(() => { (expiry![0] as () => void)() })
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    expect(screen.getByText(/Tu sesión venció/)).toBeVisible()
    expect(screen.queryByText('ana@example.com')).not.toBeInTheDocument()
  })

  it('descuenta del plazo el tiempo empleado en login', async () => {
    const start = Date.now()
    const now = vi.spyOn(Date, 'now').mockReturnValue(start)
    server.use(http.post('/api/v1/auth/login', () => {
      now.mockReturnValue(start + 5000)
      return HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false })
    }))
    const timers = vi.spyOn(globalThis, 'setTimeout')
    setup()
    await enter()
    expect(timers.mock.calls.some(([, delay]) => delay === 895000)).toBe(true)
  })

  it.each(['focus', 'visibilitychange'])('detecta reloj vencido al recuperar %s sin consultar me', async event => {
    const start = Date.now()
    const now = vi.spyOn(Date, 'now').mockReturnValue(start)
    setup()
    await enter()
    const me = vi.fn(() => HttpResponse.json(testUser))
    server.use(http.get('/api/v1/auth/me', me))
    now.mockReturnValue(start + 900001)
    if (event === 'focus') fireEvent(window, new Event('focus'))
    else {
      vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
      fireEvent(document, new Event('visibilitychange'))
    }
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    expect(me).not.toHaveBeenCalled()
  })

  it('401 de me invalida inmediatamente la sesión', async () => {
    setup()
    await enter()
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ error: { codigo: 'AUTENTICACION_REQUERIDA' } }, { status: 401 })))
    fireEvent(window, new Event('focus'))
    await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
    expect(screen.getByText(/dejó de ser válida/)).toBeVisible()
  })

  it('403 de me informa permiso denegado sin cerrar sesión', async () => {
    setup()
    await enter()
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ error: { codigo: 'PERMISO_DENEGADO', mensaje: 'secret-not-for-ui' } }, { status: 403 })))
    fireEvent(window, new Event('focus'))
    expect(await screen.findByText('No tenés permiso para realizar esta consulta.')).toBeVisible()
    expect(screen.getByTestId('session-status')).toHaveTextContent('authenticated')
    expect(screen.queryByText('secret-not-for-ui')).not.toBeInTheDocument()
  })

  it('error de red al refrescar conserva últimos datos sin fingir actualización', async () => {
    setup()
    await enter()
    server.use(http.get('/api/v1/auth/me', () => HttpResponse.error()))
    fireEvent(window, new Event('focus'))
    expect(await screen.findByText(/Se muestran los últimos datos verificados/)).toBeVisible()
    expect(screen.getByTestId('session-status')).toHaveTextContent('authenticated')
  })
})
