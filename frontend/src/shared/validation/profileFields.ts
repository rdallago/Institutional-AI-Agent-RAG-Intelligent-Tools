// Python str.strip whitespace, including U+0085/U+001C..1F and excluding BOM.
const whitespace = new Set([
  ...Array.from({ length: 5 }, (_, i) => i + 9), ...Array.from({ length: 5 }, (_, i) => i + 28),
  0x85, 0xa0, 0x1680, ...Array.from({ length: 11 }, (_, i) => 0x2000 + i), 0x2028, 0x2029, 0x202f, 0x205f, 0x3000,
])
const strip = (value: string) => {
  const chars = [...value]
  let start = 0, end = chars.length
  while (start < end && whitespace.has(chars[start].codePointAt(0)!)) start++
  while (end > start && whitespace.has(chars[end - 1].codePointAt(0)!)) end--
  return chars.slice(start, end).join('')
}
export function validateName(value: string): true | string {
  const length = [...strip(value)].length
  return length >= 1 && length <= 100 || 'Debe contener entre 1 y 100 caracteres, sin contar espacios externos.'
}
export function validateEmail(value: string): true | string {
  const invalid = 'Ingresá un email ASCII válido, de hasta 254 caracteres.'
  if (/[^\x20-\x7e]/.test(value)) return invalid
  const email = value.replace(/^ +| +$/g, '').toLowerCase()
  const parts = email.split('@')
  if (email.length > 254 || parts.length !== 2) return invalid
  const [local, domain] = parts
  if (!local || local.length > 64 || !/^[a-z0-9!#$%&'*+/=?^_`{|}~.-]+$/.test(local)
    || local.startsWith('.') || local.endsWith('.') || local.includes('..')) return invalid
  const labels = domain.split('.')
  return domain.length >= 1 && domain.length <= 253 && labels.length >= 2
    && labels.every(label => label.length >= 1 && label.length <= 63 && /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label)) || invalid
}
