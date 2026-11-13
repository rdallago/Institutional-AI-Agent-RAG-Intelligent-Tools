import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { expect, it, vi } from 'vitest'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { AppProviders } from '../../app/providers'
import { AppRoutes } from '../../router/routes'
import { useAuth } from '../auth/model/authContext'
import { server } from '../../test/mocks/server'
import { testUser } from '../../test/mocks/handlers'

const INITIAL = 'inicial manual ficticia de prueba'
const profile = { ...testUser, id: '00000000-0000-0000-0000-000000000003', nombre: 'Diego', email: 'diego@example.com', rol: 'USUARIO' }
function Controls({ path }: { path: string }) {
  const { login, state } = useAuth()
  const navigate = useNavigate()
  return <>
    <output data-testid="status">{state.status}</output>
    <button onClick={() => { void login({ email: 'ana@example.com', password: INITIAL }).catch(() => {}) }}>Acceso de prueba</button>
    <button onClick={() => navigate(path)}>Abrir operación</button>
  </>
}
function setup(path: string, active = true) {
  server.use(http.get('/api/v1/usuarios/:id', () => HttpResponse.json({ ...profile, activo: active })))
  render(<AppProviders><MemoryRouter><Controls path={path} /><AppRoutes /></MemoryRouter></AppProviders>)
}
async function enter() {
  fireEvent.click(screen.getByText('Acceso de prueba'))
  await screen.findByRole('heading', { name: 'Bienvenido, Ana' })
  fireEvent.click(screen.getByText('Abrir operación'))
}
function passwords(confirmation = INITIAL) {
  fireEvent.change(screen.getByLabelText('Contraseña inicial'), { target: { value: INITIAL } })
  fireEvent.change(screen.getByLabelText('Confirmar contraseña inicial'), { target: { value: confirmation } })
}
async function detail() {
  setup(`/usuarios/${profile.id}`); await enter()
  fireEvent.click(await screen.findByRole('button', { name: 'Asignar contraseña inicial' }))
  return screen.findByRole('dialog')
}

it('alta exige inicial y confirmación sin enviar campos extra', async () => {
  const post = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.json()).toEqual({ nombre: 'Diego', apellido: 'Prueba', email: 'diego@example.com', rol: 'USUARIO', password_inicial: INITIAL })
    return HttpResponse.json(profile, { status: 201 })
  })
  server.use(http.post('/api/v1/usuarios', post))
  setup('/usuarios/nuevo'); await enter()
  fireEvent.change(await screen.findByLabelText('Nombre'), { target: { value: 'Diego' } })
  fireEvent.change(screen.getByLabelText('Apellido'), { target: { value: 'Prueba' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'diego@example.com' } })
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  expect(await screen.findByText('Usá entre 15 y 128 caracteres Unicode.')).toBeVisible()
  expect(post).not.toHaveBeenCalled()
  passwords('distinta')
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  expect(await screen.findByText('Las contraseñas deben coincidir exactamente.')).toBeVisible()
  expect(post).not.toHaveBeenCalled()
  passwords()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  await screen.findByText('Perfil creado correctamente.')
  expect(post).toHaveBeenCalledTimes(1)
  expect(screen.queryByLabelText('Contraseña inicial')).not.toBeInTheDocument()
})

it('barrera cerrada en alta no simula éxito y limpia secretos, sin cerrar sesión', async () => {
  const post = vi.fn(() => HttpResponse.json({ error: { codigo: 'APROVISIONAMIENTO_NO_HABILITADO', mensaje: INITIAL } }, { status: 403 }))
  server.use(http.post('/api/v1/usuarios', post))
  setup('/usuarios/nuevo'); await enter()
  fireEvent.change(await screen.findByLabelText('Nombre'), { target: { value: 'Diego' } })
  fireEvent.change(screen.getByLabelText('Apellido'), { target: { value: 'Prueba' } })
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'diego@example.com' } })
  passwords()
  fireEvent.click(screen.getByRole('button', { name: 'Crear perfil' }))
  expect(await screen.findByText('El aprovisionamiento de contraseñas iniciales todavía no está habilitado. No se realizó la operación.')).toBeVisible()
  expect(screen.getByLabelText('Contraseña inicial')).toHaveValue('')
  expect(screen.getByLabelText('Confirmar contraseña inicial')).toHaveValue('')
  expect(screen.getByLabelText('Nombre')).toHaveValue('Diego')
  expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
  expect(screen.queryByText(INITIAL)).not.toBeInTheDocument()
  expect(post).toHaveBeenCalledTimes(1)
})

it('asignación explícita no inventa presencia de credencial y envía solo la inicial', async () => {
  const post = vi.fn(async ({ request }: { request: Request }) => {
    expect(await request.json()).toEqual({ password_inicial: INITIAL })
    return new HttpResponse(null, { status: 204 })
  })
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  server.use(http.post('/api/v1/usuarios/:id/credencial-inicial', post))
  const dialog = await detail()
  expect(within(dialog).getByText(/El servidor comprobará esta condición/)).toBeVisible()
  expect(screen.queryByText('Sin credencial')).not.toBeInTheDocument()
  passwords()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar asignación' }))
  expect(await screen.findByText('Contraseña inicial asignada. El usuario deberá cambiarla al ingresar.')).toBeVisible()
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(post).toHaveBeenCalledTimes(1)
  expect(storage).not.toHaveBeenCalled()
})

it.each([
  ['APROVISIONAMIENTO_NO_HABILITADO', 403, 'El aprovisionamiento de contraseñas iniciales todavía no está habilitado. No se realizó la operación.'],
  ['CREDENCIAL_EXISTENTE', 409, 'El perfil ya tiene una credencial. Esta acción no permite reemplazarla ni restablecer contraseñas.'],
  ['USUARIO_INACTIVO_NO_APROVISIONABLE', 409, 'El perfil debe estar activo para asignar una contraseña inicial. La reactivación es una operación separada.'],
] as const)('asignación maneja %s sin reset ni éxito ficticio', async (code, status, message) => {
  const post = vi.fn(() => HttpResponse.json({ error: { codigo: code, mensaje: INITIAL } }, { status }))
  server.use(http.post('/api/v1/usuarios/:id/credencial-inicial', post))
  const dialog = await detail(); passwords()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar asignación' }))
  expect(await screen.findByText(message)).toBeVisible()
  expect(screen.getByLabelText('Contraseña inicial')).toHaveValue('')
  expect(screen.getByTestId('status')).toHaveTextContent('authenticated')
  expect(screen.queryByText(INITIAL)).not.toBeInTheDocument()
  expect(post).toHaveBeenCalledTimes(1)
})

it('asignación ambigua limpia secretos y bloquea reenvío', async () => {
  const post = vi.fn(() => HttpResponse.error())
  server.use(http.post('/api/v1/usuarios/:id/credencial-inicial', post))
  const dialog = await detail(); passwords()
  fireEvent.click(within(dialog).getByRole('button', { name: 'Confirmar asignación' }))
  expect(await screen.findByText(/No se pudo confirmar la asignación/)).toBeVisible()
  expect(screen.getByLabelText('Contraseña inicial')).toHaveValue('')
  expect(within(dialog).getByRole('button', { name: 'Confirmar asignación' })).toBeDisabled()
  expect(post).toHaveBeenCalledTimes(1)
})

it('perfil inactivo no ofrece una asignación funcional ni implica ausencia de credencial', async () => {
  setup(`/usuarios/${profile.id}`, false); await enter()
  expect(await screen.findByRole('button', { name: 'Asignar contraseña inicial' })).toBeDisabled()
  expect(screen.getByText('El perfil debe estar activo para asignar una contraseña inicial.')).toBeVisible()
  expect(screen.queryByText('Sin credencial')).not.toBeInTheDocument()
})
