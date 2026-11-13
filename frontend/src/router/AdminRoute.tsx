import { Alert, Typography } from '@mui/material'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../features/auth/model/authContext'

export function AdminRoute() {
  const { state } = useAuth()
  if (state.status === 'passwordChangeRequired') return <Navigate to="/cambiar-password" replace />
  if (state.status !== 'authenticated') return null
  if (state.user.rol !== 'ADMIN') return <section>
    <Typography component="h1" variant="h4" sx={{ mb: 2 }}>Acceso restringido</Typography>
    <Alert severity="warning">No tenés permiso para acceder a esta sección.</Alert>
  </section>
  return <Outlet />
}
