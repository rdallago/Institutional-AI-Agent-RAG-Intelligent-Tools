import { http, HttpResponse } from 'msw'
import { expect, it } from 'vitest'
import { server } from '../test/mocks/server'
import { createHttpClient } from './httpClient'
import { validateApiBase } from '../app/config'

it('rechaza bases externas y rutas capaces de escapar del backend', async () => {
  for (const base of ['http://127.0.0.1:8000/api/v1', '//third-party/api', '/other']) {
    expect(() => validateApiBase(base)).toThrow()
    expect(() => createHttpClient(base, () => 'fictional')).toThrow()
  }
  const client = createHttpClient('/api/v1', () => 'fictional')
  for (const path of ['//third-party/path', '/../../outside', 'https://third-party']) {
    await expect(client(path, { authenticated: true })).rejects.toThrow('Ruta de API no permitida.')
  }
})

it('reconoce 204 sin parsear JSON', async () => {
  server.use(http.post('/api/v1/empty', () => new HttpResponse(null, { status: 204 })))
  await expect(createHttpClient('/api/v1', () => null)('/empty', { method: 'POST' })).resolves.toBeUndefined()
})

it('distingue cancelación de error de red', async () => {
  const controller = new AbortController()
  controller.abort()
  await expect(createHttpClient('/api/v1', () => null)('/auth/me', { signal: controller.signal }))
    .rejects.toMatchObject({ kind: 'cancelled' })
})
