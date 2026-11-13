import { http, HttpResponse } from 'msw'

export const testToken = 'fictional-access-token-for-msw-only'
export const testUser = {
  id: '550e8400-e29b-41d4-a716-446655440000', nombre: 'Ana', apellido: 'Pruebas',
  email: 'ana@example.com', activo: true, rol: 'ADMIN', fecha_creacion: '2026-01-01T12:00:00Z', debe_cambiar_password: false,
}
export const handlers = [
  http.get('/api/v1/ia/conversaciones', () => HttpResponse.json([])),
  http.get('/api/v1/ia/documentos', () => HttpResponse.json([])),
  http.get('/api/v1/usuarios', () => HttpResponse.json([])),
  http.post('/api/v1/auth/logout', () => new HttpResponse(null, { status: 204 })),
  http.post('/api/v1/auth/login', () => HttpResponse.json({ access_token: testToken, token_type: 'bearer', expires_in: 900, debe_cambiar_password: false })),
  http.get('/api/v1/auth/me', ({ request }) => request.headers.get('Authorization') === `Bearer ${testToken}`
    ? HttpResponse.json(testUser)
    : HttpResponse.json({ error: { codigo: 'AUTENTICACION_REQUERIDA' } }, { status: 401 })),
]
