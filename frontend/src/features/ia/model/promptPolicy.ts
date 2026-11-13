// Whitespace reconocido por str.strip de Python; conservar el texto original valido.
function isWhitespace(point: string) {
  const code = point.codePointAt(0)!
  return (code >= 9 && code <= 13) || (code >= 28 && code <= 32)
    || (code >= 0x2000 && code <= 0x200a)
    || [0x85, 0xa0, 0x1680, 0x2028, 0x2029, 0x202f, 0x205f, 0x3000].includes(code)
}

export function textMetrics(value: string) {
  const points = [...value]
  const unicode = !points.some(point => point.length === 1 && point.charCodeAt(0) >= 0xd800 && point.charCodeAt(0) <= 0xdfff)
  return { points: points.length, unicode, bytes: unicode ? new TextEncoder().encode(value).length : null,
    nonBlank: !points.every(isWhitespace), nul: value.includes('\0') }
}

export function validatePrompt(value: string): true | string {
  const metrics = textMetrics(value)
  if (!metrics.nonBlank) return 'Escribí una consulta; no puede contener solo espacios.'
  if (!metrics.unicode) return 'La consulta debe contener Unicode válido.'
  if (metrics.nul) return 'La consulta contiene un carácter NUL no permitido.'
  if (metrics.points > 1000) return 'La consulta admite hasta 1000 caracteres Unicode.'
  if (metrics.bytes !== null && metrics.bytes > 3000) return 'La consulta admite hasta 3000 bytes UTF-8.'
  return true
}
