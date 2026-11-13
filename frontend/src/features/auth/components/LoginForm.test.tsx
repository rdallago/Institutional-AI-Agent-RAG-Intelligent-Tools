import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import { renderApp } from '../../../test/renderWithProviders'
import { server } from '../../../test/mocks/server'
import { testToken, testUser } from '../../../test/mocks/handlers'

async function fill() {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Email'), 'ana@example.com')
  // Deliberately shorter than the new-password minimum: login must not impose it.
  await user.type(screen.getByLabelText('Contraseña'), 'test')
  return user
}

describe('primer login funcional', () => {
  it('presenta campos y no ofrece funcionalidades inexistentes ni política de alta', () => {
    renderApp()
    expect(screen.getByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
    expect(screen.getByLabelText('Email')).toHaveAttribute('autocomplete', 'username')
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'current-password')
    expect(screen.queryByText(/15 caracteres|registrarse|olvidé/i)).not.toBeInTheDocument()
  })

  it('valida campos obligatorios sin enviar HTTP', async () => {
    const request = vi.fn()
    server.use(http.post('/api/v1/auth/login', request))
    renderApp()
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByText('Ingresá tu email.')).toBeVisible()
    expect(screen.getByText('Ingresá tu contraseña.')).toBeVisible()
    expect(request).not.toHaveBeenCalled()
  })

  it('permite mostrar y ocultar contraseña sin alterar el valor', async () => {
    renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Mostrar contraseña' }))
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('type', 'text')
    expect(screen.getByLabelText('Contraseña')).toHaveValue('test')
    await user.click(screen.getByRole('button', { name: 'Ocultar contraseña' }))
    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('type', 'password')
  })

  it('envía JSON y no Bearer en login; valida me con Bearer antes de mostrar identidad', async () => {
    const calls: string[] = []
    server.use(
      http.post('/api/v1/auth/login', async ({ request }) => {
        calls.push('login')
        expect(request.headers.get('Authorization')).toBeNull()
        expect(request.headers.get('Content-Type')).toBe('application/json')
        expect(await request.json()).toEqual({ email: 'ana@example.com', password: 'test' })
        return HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false })
      }),
      http.get('/api/v1/auth/me', ({ request }) => {
        calls.push('me')
        expect(request.headers.get('Authorization')).toBe(`Bearer ${testToken}`)
        return HttpResponse.json(testUser)
      }),
    )
    renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByRole('heading', { name: 'Bienvenido, Ana' })).toBeVisible()
    expect(screen.getByText('Ana Pruebas')).toBeVisible()
    expect(screen.getByText('ana@example.com')).toBeVisible()
    expect(screen.getByText('ADMIN')).toBeVisible()
    expect(calls).toEqual(['login', 'me'])
  })

  it('no autentica mientras me esté pendiente y bloquea doble envío', async () => {
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    const login = vi.fn(() => HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false }))
    server.use(http.post('/api/v1/auth/login', login), http.get('/api/v1/auth/me', async () => {
      await gate
      return HttpResponse.json(testUser)
    }))
    renderApp()
    const user = await fill()
    const button = screen.getByRole('button', { name: 'Ingresar' })
    await user.dblClick(button)
    expect(await screen.findByRole('button', { name: 'Verificando perfil…' })).toBeDisabled()
    expect(screen.queryByText('Bienvenido, Ana')).not.toBeInTheDocument()
    fireEvent.submit(button.closest('form')!)
    expect(login).toHaveBeenCalledTimes(1)
    release()
    expect(await screen.findByText('Bienvenido, Ana')).toBeVisible()
  })

  it.each([401, 422, 500])('presenta error %s sin reproducir secretos del servidor', async status => {
    server.use(http.post('/api/v1/auth/login', () => HttpResponse.json({ error: {
      codigo: 'ERROR', mensaje: 'sensitive-server-message', password: 'do-not-show',
    } }, { status })))
    renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toBeVisible()
    expect(alert.textContent).not.toMatch(/sensitive|do-not-show/)
    expect(screen.getByLabelText('Contraseña')).toHaveValue('')
    expect(screen.queryByText('Bienvenido, Ana')).not.toBeInTheDocument()
  })

  it('respeta Retry-After de 429 y permite reintentar al terminar', async () => {
    server.use(http.post('/api/v1/auth/login', () => HttpResponse.json({ error: { codigo: 'LIMITE_INTENTOS' } },
      { status: 429, headers: { 'Retry-After': '2' } })))
    renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Demasiados intentos')
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeDisabled()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Ingresar' })).toBeEnabled(), { timeout: 4000 })
  })

  it('distingue error de red', async () => {
    server.use(http.post('/api/v1/auth/login', () => HttpResponse.error()))
    renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No pudimos conectar')
  })

  it.each(['html', 'invalid-token', 'invalid-profile', 'me-401', 'me-500'])('rechaza respuesta inesperada o me fallido: %s', async scenario => {
    if (scenario === 'html') server.use(http.post('/api/v1/auth/login', () => new HttpResponse('<html>unexpected</html>')))
    if (scenario === 'invalid-token') server.use(http.post('/api/v1/auth/login', () => HttpResponse.json({ access_token: testToken })))
    if (scenario === 'invalid-profile') server.use(http.get('/api/v1/auth/me', () => HttpResponse.json({ ...testUser, rol: 'SUPERADMIN' })))
    if (scenario === 'me-401' || scenario === 'me-500') server.use(http.get('/api/v1/auth/me', () => new HttpResponse(null, { status: scenario === 'me-401' ? 401 : 500 })))
    renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByRole('alert')).toBeVisible()
    expect(screen.queryByText('Bienvenido, Ana')).not.toBeInTheDocument()
  })

  it('no persiste JWT y un nuevo montaje exige login aunque la URL sea dashboard', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    const cookies = vi.spyOn(Document.prototype, 'cookie', 'set')
    const indexed = vi.spyOn(window.indexedDB ?? { open: () => undefined }, 'open')
    const view = renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    expect(await screen.findByText('Bienvenido, Ana')).toBeVisible()
    expect(storage).not.toHaveBeenCalled()
    expect(cookies).not.toHaveBeenCalled()
    expect(indexed).not.toHaveBeenCalled()
    view.unmount()
    renderApp('/dashboard')
    expect(await screen.findByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
  })

  it('ignora una respuesta tardía tras desmontar el proveedor', async () => {
    let release!: () => void
    const gate = new Promise<void>(resolve => { release = resolve })
    let started = false
    const me = vi.fn(() => HttpResponse.json(testUser))
    server.use(http.post('/api/v1/auth/login', async () => {
      started = true
      await gate
      return HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false })
    }), http.get('/api/v1/auth/me', me))
    const view = renderApp()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: 'Ingresar' }))
    await waitFor(() => expect(started).toBe(true))
    view.unmount()
    renderApp('/dashboard')
    await act(async () => { release(); await gate })
    expect(screen.getByRole('heading', { name: 'Ingresá a tu cuenta' })).toBeVisible()
    expect(me).not.toHaveBeenCalled()
  })
})
