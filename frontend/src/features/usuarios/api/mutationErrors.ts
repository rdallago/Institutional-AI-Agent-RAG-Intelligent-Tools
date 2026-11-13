import { ApiError } from '../../../api/errors'

export function ambiguousMutation(error: unknown) {
  return error instanceof ApiError && (error.kind === 'network' || error.kind === 'contract' || (error.status ?? 0) >= 500)
}
export function mutationMessage(error: unknown): string {
  if (ambiguousMutation(error)) return 'No pudimos confirmar el resultado. La operación puede haberse aplicado. Consultá el perfil o el listado antes de volver a enviar.'
  if (!(error instanceof ApiError)) return 'No se pudo completar la operación.'
  if (error.code === 'APROVISIONAMIENTO_NO_HABILITADO') return 'El aprovisionamiento de contraseñas iniciales todavía no está habilitado. No se realizó la operación.'
  if (error.code === 'CREDENCIAL_EXISTENTE') return 'El perfil ya tiene una credencial. Esta acción no permite reemplazarla ni restablecer contraseñas.'
  if (error.code === 'USUARIO_INACTIVO_NO_APROVISIONABLE') return 'El perfil debe estar activo para asignar una contraseña inicial. La reactivación es una operación separada.'
  if (error.status === 403) return 'No tenés permiso para realizar esta operación.'
  if (error.status === 404) return 'El perfil no está disponible.'
  if (error.code === 'USUARIO_ACTIVO_EXISTENTE') return 'Ya existe un perfil activo con ese email.'
  if (error.code === 'USUARIO_INACTIVO_REACTIVABLE') return 'El email pertenece a un perfil inactivo. Podés revisarlo y reactivarlo por separado, sin sobrescribir sus datos.'
  if (error.code === 'EMAIL_EN_USO') return 'El email pertenece a otro perfil.'
  if (error.status === 422) return 'Revisá los campos indicados. Los datos no cumplen las validaciones del servidor.'
  return 'No se pudo completar la operación. Revisá los datos o consultá el estado del perfil.'
}
