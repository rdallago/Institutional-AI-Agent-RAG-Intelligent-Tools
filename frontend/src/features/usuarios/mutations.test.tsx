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
import { validateEmail, validateName } from '../../shared/validation/profileFields'

const profile = { ...testUser, id: '00000000-0000-0000-0000-000000000003', nombre: 'Diego', apellido: 'Ficticio', email: 'diego@example.com', rol: 'USUARIO' }
function Controls({ path }: { path: string }) {
  const { login, state } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  return <div>
    <output data-testid="auth-status">{state.status}</output><output data-testid="url">{location.pathname}{location.search}</output>
    <button onClick={() => { void login({ email: 'ana@example.com', password: 'ficticia para pruebas' }).catch(() => {}) }}>Acceso de prueba</button>
    <button onClick={() => navigate(path)}>Abrir operación</button>
    <button onClick={() => navigate('/usuarios/nuevo')}>Otra alta</button>
  </div>
}
function setup(path = '/usuarios/nuevo') {
  return render(<AppProviders><MemoryRouter><Controls path={path} /><AppRoutes /></MemoryRouter></AppProviders>)
}
async function enter() {
  fireEvent.click(screen.getByText('Acceso de prueba'))
  await screen.findByRole('heading', { name: 'Bienvenido, Ana' })
  fireEvent.click(screen.getByText('Abrir operación'))
}
async function fill() {
  await screen.findByLabelText('Nombre')
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Diego' } })
  fireEvent.change(screen.getByLabelText('Apellido'), { target: { value: 'Ficticio' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'diego@example.com' } })
  if (screen.queryByLabelText('Contrase\u00f1a inicial')) {
    fireEvent.change(screen.getByLabelText('Contrase\u00f1a inicial'), { target: { value: 'ficticia inicial de pruebas' } })
    fireEvent.change(screen.getByLabelText('Confirmar contrase\u00f1a inicial'), { target: { value: 'ficticia inicial de pruebas' } })
  }
}
function detailStore(initial = profile) {
  const store = { user: { ...initial }, reads: 0 }
  server.use(http.get('/api/v1/usuarios/:id', () => { store.reads++; return HttpResponse.json(store.user) }))
  return store
}
async function openDetail() {
  await screen.findByRole('heading', { name: 'Detalle de perfil' })
  await screen.findByText('diego@example.com')
}

it('crea con USUARIO predeterminado, muestra detalle y refresca listado al volver', async () => {
  const store = detailStore()
  let input: unknown
  server.use(http.post('/api/v1/usuarios', async ({ request }) => {
    expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
    input = await request.json()
    return HttpResponse.json(store.user, { status: 201 })
  }), http.get('/api/v1/usuarios', () => HttpResponse.json([store.user])))
  setup('/usuarios/nuevo?estado=todos&limite=10&desplazamiento=0')
  await enter()
  expect(await screen.findByText('El administrador establece una contraseña inicial. El usuario deberá cambiarla antes de acceder a la aplicación. La disponibilidad del aprovisionamiento depende de la habilitación del servidor.')).toBeVisible()
  expect(screen.queryByLabelText('Contraseña')).not.toBeInTheDocument()
  await fill()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  await openDetail()
  expect(input).toEqual({ nombre: 'Diego', apellido: 'Ficticio', email: 'diego@example.com', rol: 'USUARIO', password_inicial: 'ficticia inicial de pruebas' })
  expect(screen.getByText('Perfil creado correctamente.')).toBeVisible()
  fireEvent.click(screen.getByRole('link', { name: 'Volver al listado' }))
  expect(await screen.findAllByText('diego@example.com')).not.toHaveLength(0)
  expect(screen.getByTestId('url')).toHaveTextContent('estado=todos&limite=10&desplazamiento=0')
})

it('permite elegir rol ADMIN solo en alta', async () => {
  let input: unknown
  detailStore({ ...profile, rol: 'ADMIN' })
  server.use(http.post('/api/v1/usuarios', async ({ request }) => { input = await request.json(); return HttpResponse.json({ ...profile, rol: 'ADMIN' }, { status: 201 }) }))
  setup()
  await enter()
  await fill()
  const user = userEvent.setup()
  await user.click(screen.getByRole('combobox', { name: 'Rol' }))
  await user.click(await screen.findByRole('option', { name: 'ADMIN' }))
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  await openDetail()
  expect(input).toMatchObject({ rol: 'ADMIN' })
})

it('valida campos obligatorios, longitudes y email sin enviar escrituras', async () => {
  const post = vi.fn(() => HttpResponse.json(profile, { status: 201 }))
  server.use(http.post('/api/v1/usuarios', post))
  setup()
  await enter()
  fireEvent.click(await screen.findByRole('button', { name: 'Crear perfil' }))
  expect((await screen.findAllByText(/Debe contener entre 1 y 100/)).length).toBe(2)
  expect(post).not.toHaveBeenCalled()
  await fill()
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'x'.repeat(101) } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'inválido@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  expect(await screen.findByText(/Ingresá un email ASCII válido/)).toBeVisible()
  expect(post).not.toHaveBeenCalled()
})

it('edita un inactivo con PUT exacto, sin enviar rol, estado, id ni fecha', async () => {
  const store = detailStore({ ...profile, activo: false })
  let input: unknown
  server.use(http.put('/api/v1/usuarios/:id', async ({ request }) => {
    input = await request.json()
    store.user = { ...store.user, nombre: 'Diana' }
    return HttpResponse.json(store.user)
  }))
  setup(`/usuarios/${profile.id}/editar`)
  await enter()
  expect(await screen.findByLabelText('Nombre')).toHaveValue('Diego')
  expect(screen.getByText(/Estado: Inactivo/)).toBeVisible()
  expect(screen.queryByRole('combobox', { name: 'Rol' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Diana' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
  await openDetail()
  expect(input).toEqual({ nombre: 'Diana', apellido: 'Ficticio', email: 'diego@example.com' })
  expect(screen.getByText('Diana')).toBeVisible()
  expect(screen.getByText('Inactivo')).toBeVisible()
  expect(screen.getByText('Perfil actualizado correctamente.')).toBeVisible()
  expect(store.reads).toBe(2)
})

it('EMAIL_EN_USO al editar mantiene todos los valores y muestra error en email', async () => {
  detailStore()
  server.use(http.put('/api/v1/usuarios/:id', () => HttpResponse.json({ error: { codigo: 'EMAIL_EN_USO', mensaje: 'private-data' } }, { status: 409 })))
  setup(`/usuarios/${profile.id}/editar`)
  await enter()
  await fill()
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'nuevo@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
  expect(await screen.findByText('El email pertenece a otro perfil.')).toBeVisible()
  expect(screen.getByLabelText('Email')).toHaveValue('nuevo@example.com')
  expect(screen.getByLabelText('Nombre')).toHaveValue('Diego')
  expect(screen.queryByText('private-data')).not.toBeInTheDocument()
})

it.each(['USUARIO_ACTIVO_EXISTENTE', 'USUARIO_INACTIVO_REACTIVABLE'])(
  '409 %s conserva alta y nunca reactiva automáticamente', async code => {
    const patch = vi.fn(() => HttpResponse.json(profile))
    server.use(http.post('/api/v1/usuarios', () => HttpResponse.json({ error: { codigo: code, usuario_id: profile.id } }, { status: 409 })), http.patch('/api/v1/usuarios/:id/reactivar', patch))
    setup()
    await enter()
    await fill()
    fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
    expect(await screen.findByText(code === 'USUARIO_ACTIVO_EXISTENTE'
      ? 'Ya existe un perfil activo con ese email.'
      : 'El email pertenece a un perfil inactivo. Podés revisarlo y reactivarlo por separado, sin sobrescribir sus datos.')).toBeVisible()
    await waitFor(() => expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true'))
    expect(screen.getByLabelText('Email')).toHaveValue('diego@example.com')
    expect(patch).not.toHaveBeenCalled()
    if (code === 'USUARIO_INACTIVO_REACTIVABLE') {
      expect(screen.getByRole('link', { name: 'Revisar perfil inactivo' })).toHaveAttribute('href', expect.stringContaining(profile.id))
    }
  })

it('conflicto inactivo permite revisar y confirmar reactivación separada sin sobrescribir campos', async () => {
  const store = detailStore({ ...profile, nombre: 'Existente', activo: false })
  const put = vi.fn()
  const patch = vi.fn(() => { store.user = { ...store.user, activo: true }; return HttpResponse.json(store.user) })
  server.use(http.post('/api/v1/usuarios', () => HttpResponse.json({ error: { codigo: 'USUARIO_INACTIVO_REACTIVABLE', usuario_id: profile.id } }, { status: 409 })),
    http.patch('/api/v1/usuarios/:id/reactivar', patch), http.put('/api/v1/usuarios/:id', put))
  setup()
  await enter()
  await fill()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  fireEvent.click(await screen.findByRole('link', { name: 'Revisar perfil inactivo' }))
  await openDetail()
  expect(screen.getByText('Existente')).toBeVisible()
  expect(patch).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Reactivar' }))
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Confirmar operación' }))
  await waitFor(() => expect(screen.getByText('Activo')).toBeVisible())
  expect(store.user.nombre).toBe('Existente')
  expect(put).not.toHaveBeenCalled()
  expect(patch).toHaveBeenCalledTimes(1)
})

it('baja pide confirmación, admite cancelar y refresca detalle y listado tras 204', async () => {
  const store = detailStore()
  const remove = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.text()).toBe('')
    store.user = { ...store.user, activo: false }
    return new HttpResponse(null, { status: 204 })
  })
  server.use(http.delete('/api/v1/usuarios/:id', remove), http.get('/api/v1/usuarios', () => HttpResponse.json([store.user])))
  setup(`/usuarios/${profile.id}?estado=todos&limite=10&desplazamiento=0`)
  await enter()
  await openDetail()
  fireEvent.click(screen.getByRole('button', { name: 'Dar de baja' }))
  let dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('Diego Ficticio')
  expect(dialog).toHaveTextContent('diego@example.com')
  expect(dialog).toHaveTextContent('no elimina físicamente')
  expect(dialog).toHaveTextContent('sesiones existentes')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(remove).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Dar de baja' }))
  dialog = await screen.findByRole('dialog')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar operación' }))
  expect(await screen.findByText('Baja lógica aplicada. Las sesiones del perfil fueron revocadas.')).toBeVisible()
  expect(await screen.findByText('Inactivo')).toBeVisible()
  expect(remove).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('link', { name: 'Volver al listado' }))
  expect(await screen.findAllByText('Inactivo')).not.toHaveLength(0)
})

it('reactiva con confirmación, sin restaurar sesiones ni crear credenciales', async () => {
  const store = detailStore({ ...profile, activo: false })
  const patch = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.text()).toBe('')
    store.user = { ...store.user, activo: true }
    return HttpResponse.json(store.user)
  })
  server.use(http.patch('/api/v1/usuarios/:id/reactivar', patch))
  setup(`/usuarios/${profile.id}`)
  await enter()
  await openDetail()
  expect(screen.queryByRole('button', { name: 'Dar de baja' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Reactivar' }))
  const dialog = await screen.findByRole('dialog')
  expect(dialog).toHaveTextContent('no restaura sesiones anteriores ni asigna credenciales nuevas')
  expect(patch).not.toHaveBeenCalled()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar operación' }))
  expect(await screen.findByText('Perfil reactivado. Las sesiones anteriores siguen revocadas.')).toBeVisible()
  expect(await screen.findByRole('button', { name: 'Dar de baja' })).toBeVisible()
  expect(patch).toHaveBeenCalledTimes(1)
})

it('ADMIN no puede darse de baja a sí mismo', async () => {
  detailStore(testUser)
  const remove = vi.fn()
  server.use(http.delete('/api/v1/usuarios/:id', remove))
  setup(`/usuarios/${testUser.id}`)
  await enter()
  const button = await screen.findByRole('button', { name: 'Dar de baja' })
  expect(button).toBeDisabled()
  expect(screen.getByText('No podés dar de baja tu propio perfil administrativo.')).toBeVisible()
  fireEvent.click(button)
  expect(remove).not.toHaveBeenCalled()
})

it('error 403 de baja cierra confirmación y mantiene el error visible sin cerrar sesión', async () => {
  detailStore()
  const remove = vi.fn(() => HttpResponse.json({ error: { codigo: 'PERMISO_DENEGADO' } }, { status: 403 }))
  server.use(http.delete('/api/v1/usuarios/:id', remove))
  setup(`/usuarios/${profile.id}`)
  await enter(); await openDetail()
  fireEvent.click(screen.getByRole('button', { name: 'Dar de baja' }))
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Confirmar operación' }))
  expect(await screen.findByText('No tenés permiso para realizar esta operación.')).toBeVisible()
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.getByText('Activo')).toBeVisible()
  expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated')
  expect(remove).toHaveBeenCalledTimes(1)
})

it('reactivación con red ambigua no se repite y deja revisar el estado', async () => {
  detailStore({ ...profile, activo: false })
  const patch = vi.fn(() => HttpResponse.error())
  server.use(http.patch('/api/v1/usuarios/:id/reactivar', patch))
  setup(`/usuarios/${profile.id}`)
  await enter(); await openDetail()
  fireEvent.click(screen.getByRole('button', { name: 'Reactivar' }))
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Confirmar operación' }))
  expect(await screen.findByText(/La operación puede haberse aplicado/)).toBeVisible()
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(screen.getByRole('button', { name: 'Reactivar' })).toBeDisabled()
  expect(patch).toHaveBeenCalledTimes(1)
})

it('confirmación pendiente bloquea doble baja y cancelación durante la escritura', async () => {
  const store = detailStore()
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const remove = vi.fn(async () => { await gate; store.user = { ...store.user, activo: false }; return new HttpResponse(null, { status: 204 }) })
  server.use(http.delete('/api/v1/usuarios/:id', remove))
  setup(`/usuarios/${profile.id}`)
  await enter(); await openDetail()
  fireEvent.click(screen.getByRole('button', { name: 'Dar de baja' }))
  const dialog = await screen.findByRole('dialog')
  const confirm = within(dialog).getByRole('button', { name: 'Confirmar operación' })
  fireEvent.click(confirm); fireEvent.click(confirm)
  await waitFor(() => expect(remove).toHaveBeenCalledTimes(1))
  expect(within(dialog).getByRole('button', { name: 'Aplicando…' })).toBeDisabled()
  expect(within(dialog).getByRole('button', { name: 'Cancelar' })).toBeDisabled()
  release()
  expect(await screen.findByText('Inactivo')).toBeVisible()
  expect(remove).toHaveBeenCalledTimes(1)
})

it('editar datos propios refresca la identidad del encabezado sin cambiar JWT', async () => {
  const store = detailStore(testUser)
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json(store.user)), http.put('/api/v1/usuarios/:id', async ({ request }) => {
    const data = await request.json() as { nombre: string }
    store.user = { ...store.user, nombre: data.nombre }
    return HttpResponse.json(store.user)
  }))
  setup(`/usuarios/${testUser.id}/editar`)
  await enter()
  await screen.findByLabelText('Nombre')
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Actualizada' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
  expect(await screen.findByText('Actualizada Pruebas')).toBeVisible()
  expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated')
})

it.each([403, 404, 422])('alta maneja HTTP %s sin perder datos ni reflejar secretos', async status => {
  server.use(http.post('/api/v1/usuarios', () => HttpResponse.json({ error: { codigo: 'SOLICITUD_INVALIDA', mensaje: 'secret-server', detalles: [{ campo: 'body.nombre', codigo: 'DATO_INVALIDO', mensaje: 'private' }] } }, { status })))
  setup()
  await enter()
  await fill()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  await waitFor(() => expect(screen.getByLabelText('Nombre')).toHaveAttribute('aria-invalid', 'true'))
  expect(screen.getByLabelText('Nombre')).toHaveValue('Diego')
  expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated')
  expect(screen.queryByText('secret-server')).not.toBeInTheDocument()
})

it('401 de escritura invalida sesión y elimina el formulario privado', async () => {
  server.use(http.post('/api/v1/usuarios', () => HttpResponse.json({ error: { codigo: 'AUTENTICACION_REQUERIDA' } }, { status: 401 })))
  setup()
  await enter()
  await fill()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  expect(screen.queryByLabelText('Nombre')).not.toBeInTheDocument()
})

it.each(['network', '500', 'contract'])('resultado %s ambiguo bloquea reenvío y no repite automáticamente', async scenario => {
  const post = vi.fn(() => scenario === 'network' ? HttpResponse.error() : HttpResponse.json(profile, { status: scenario === '500' ? 500 : 200 }))
  server.use(http.post('/api/v1/usuarios', post))
  setup()
  await enter()
  await fill()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  expect(await screen.findByText(/La operación puede haberse aplicado/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Crear perfil' })).toBeDisabled()
  expect(screen.getByRole('link', { name: 'Revisar listado antes de reenviar' })).toBeVisible()
  expect(screen.getByLabelText('Nombre')).toHaveValue('Diego')
  expect(post).toHaveBeenCalledTimes(1)
})

it('doble envío no duplica POST y muestra carga', async () => {
  let release!: () => void
  const gate = new Promise<void>(resolve => { release = resolve })
  const post = vi.fn(async () => { await gate; return HttpResponse.json(profile, { status: 201 }) })
  detailStore()
  server.use(http.post('/api/v1/usuarios', post))
  setup()
  await enter()
  await fill()
  const form = screen.getByLabelText('Nombre').closest('form')!
  fireEvent.submit(form); fireEvent.submit(form)
  await waitFor(() => expect(post).toHaveBeenCalledTimes(1))
  expect(screen.getByRole('button', { name: 'Guardando…' })).toBeDisabled()
  release()
  await openDetail()
  expect(post).toHaveBeenCalledTimes(1)
})

it('logout aborta la escritura pendiente y una respuesta vieja no navega en otra sesión', async () => {
  let release!: () => void
  let started = false
  let aborted = false
  const gate = new Promise<void>(resolve => { release = resolve })
  const detail = vi.fn(() => HttpResponse.json(profile))
  server.use(http.post('/api/v1/usuarios', async ({ request }) => {
    started = true
    request.signal.addEventListener('abort', () => { aborted = true })
    await gate
    return HttpResponse.json(profile, { status: 201 })
  }), http.get('/api/v1/usuarios/:id', detail))
  setup()
  await enter()
  await fill()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  await waitFor(() => expect(started).toBe(true))
  fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }))
  await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, nombre: 'Nueva' })))
  fireEvent.click(screen.getByText('Acceso de prueba'))
  await screen.findByRole('heading', { name: 'Bienvenido, Nueva' })
  await act(async () => { release(); await gate })
  expect(aborted).toBe(true)
  expect(detail).not.toHaveBeenCalled()
  expect(screen.getByTestId('url')).toHaveTextContent('/dashboard')
})

it.each(['/usuarios/nuevo', `/usuarios/${profile.id}/editar`])('USUARIO no puede abrir formulario %s ni escribir', async path => {
  const post = vi.fn(), put = vi.fn()
  server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, rol: 'USUARIO' })), http.post('/api/v1/usuarios', post), http.put('/api/v1/usuarios/:id', put))
  setup(path)
  await enter()
  expect(await screen.findByRole('heading', { name: 'Acceso restringido' })).toBeVisible()
  expect(screen.queryByLabelText('Nombre')).not.toBeInTheDocument()
  expect(post).not.toHaveBeenCalled(); expect(put).not.toHaveBeenCalled()
})

it('reglas locales conservan límites Unicode y normalización del backend', () => {
  expect(validateName('  Ana  ')).toBe(true)
  expect(validateName('😀'.repeat(100))).toBe(true)
  expect(validateName('😀'.repeat(101))).not.toBe(true)
  expect(validateName('\u0085\u001c')).not.toBe(true)
  expect(validateEmail('  VALID+tag@EXAMPLE.COM  ')).toBe(true)
  for (const value of ['ñ@example.com', '.a@example.com', 'a..b@example.com', 'a@example', 'a@-example.com', 'a@example.com\n']) expect(validateEmail(value)).not.toBe(true)
})
