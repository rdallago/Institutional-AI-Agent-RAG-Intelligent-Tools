import { Box, CircularProgress, Typography } from '@mui/material'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../features/auth/model/authContext'

export function ProtectedRoute() {
  const { state } = useAuth()
  if (state.status === 'passwordChangeRequired') return <Navigate to="/cambiar-password" replace />
  if (state.status === 'validating' || state.status === 'authenticating') return <Box role="status" sx={{ p: 5 }}><CircularProgress size={24} /><Typography>Validando sesión…</Typography></Box>
  if (state.status === 'closing') return <Box role="status" sx={{ p: 5 }}>
    <CircularProgress size={24} /><Typography>Cerrando sesión…</Typography>
  </Box>
  return state.status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace />
}
