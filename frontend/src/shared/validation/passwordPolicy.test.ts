import { expect, it } from 'vitest'
import { validateConfirmation, validateNewPassword, passwordConditions } from './passwordPolicy'

it.each([14, 129])('rechaza %i puntos de código', size => {
  expect(validateNewPassword('x'.repeat(size))).not.toBe(true)
})
it.each(['x'.repeat(15), 'x'.repeat(128), '😀'.repeat(128), ' '.repeat(15), ' é'.repeat(15)])(
  'admite límites, espacios y Unicode sin reglas de composición: %#', value => {
    expect(validateNewPassword(value)).toBe(true)
  })
it.each(['\ud800', '\udfff', 'x'.repeat(15) + '\ud800'])('rechaza Unicode inválido sin reemplazarlo: %#', value => {
  expect(passwordConditions(value).unicode).toBe(false)
  expect(validateNewPassword(value)).not.toBe(true)
})
it('mide UTF-8 y puntos de código, y no duplica la lista común del servidor', () => {
  expect(new TextEncoder().encode('😀'.repeat(128)).length).toBe(512)
  expect(passwordConditions('😀'.repeat(128))).toEqual({ length: true, unicode: true, bytes: true })
  expect(passwordConditions('😀'.repeat(129)).bytes).toBe(false)
  expect(validateNewPassword('123456789012345')).toBe(true) // El servidor decide si es común.
})
it('la confirmación preserva espacios y secuencias Unicode exactamente', () => {
  expect(validateConfirmation(' contraseña válida ', ' contraseña válida ')).toBe(true)
  expect(validateConfirmation('contraseña válida', ' contraseña válida ')).not.toBe(true)
  expect(validateConfirmation('é'.repeat(15), 'é'.repeat(15))).not.toBe(true)
  expect(validateConfirmation('', '')).not.toBe(true)
})
