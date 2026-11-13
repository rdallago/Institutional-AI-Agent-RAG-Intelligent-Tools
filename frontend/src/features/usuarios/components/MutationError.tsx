import { Alert, Button, Stack } from '@mui/material'
import { Link } from 'react-router-dom'
import { ApiError } from '../../../api/errors'
import { ambiguousMutation, mutationMessage } from '../api/mutationErrors'

export function MutationError({ error, search }: { error: unknown; search: string }) {
  if (!error) return null
  const review = error instanceof ApiError && error.status === 409 && error.code === 'USUARIO_INACTIVO_REACTIVABLE' ? error.userId : undefined
  return <Stack spacing={1}>
    <Alert severity="error">{mutationMessage(error)}</Alert>
    {review && <Button component={Link} to={`/usuarios/${review}?${search}`}>Revisar perfil inactivo</Button>}
    {ambiguousMutation(error) && <Button component={Link} to={`/usuarios?${search}`}>Revisar listado antes de reenviar</Button>}
  </Stack>
}
