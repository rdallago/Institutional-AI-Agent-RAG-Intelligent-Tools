import { Alert, Button, Stack } from '@mui/material'
import { ApiError } from '../../../api/errors'

export function ConsultaError({ error, retry }: { error: unknown; retry: () => void }) {
  const status = error instanceof ApiError ? error.status : undefined
  const message = status === 403 ? 'No tenés permiso para consultar estos perfiles.'
    : status === 404 ? 'El perfil no está disponible.'
    : status === 422 ? 'No se pudo procesar la consulta. Revisá los filtros.'
    : error instanceof ApiError && error.kind === 'contract' ? 'El servidor devolvió una respuesta inesperada.'
    : 'No pudimos obtener los datos. Revisá la conexión o intentá nuevamente.'
  return <Stack spacing={2} alignItems="flex-start">
    <Alert severity="error">{message}</Alert><Button onClick={retry}>Reintentar consulta</Button>
  </Stack>
}
