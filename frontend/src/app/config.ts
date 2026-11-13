export function validateApiBase(value: string): string {
  if (value !== '/api/v1') throw new Error('La API debe usar /api/v1 en el mismo origen.')
  return value
}

export const API_BASE_URL = validateApiBase(import.meta.env.VITE_API_BASE_URL ?? '/api/v1')
