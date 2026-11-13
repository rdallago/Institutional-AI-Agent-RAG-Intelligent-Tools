export function passwordConditions(value: string) {
  const points = [...value]
  const unicode = !points.some(point => point.length === 1 && point.charCodeAt(0) >= 0xd800 && point.charCodeAt(0) <= 0xdfff)
  return {
    length: points.length >= 15 && points.length <= 128,
    unicode,
    bytes: unicode && new TextEncoder().encode(value).length <= 512,
  }
}

export function validateNewPassword(value: string): true | string {
  const conditions = passwordConditions(value)
  if (!conditions.unicode) return 'La contraseña debe contener Unicode válido.'
  if (!conditions.length) return 'Usá entre 15 y 128 caracteres Unicode.'
  if (!conditions.bytes) return 'La contraseña admite hasta 512 bytes UTF-8.'
  return true
}

export function validateConfirmation(value: string, password: string): true | string {
  return (value.length > 0 && value === password) || 'Las contraseñas deben coincidir exactamente.'
}
