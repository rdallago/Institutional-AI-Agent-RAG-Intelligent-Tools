import { lazy } from 'react'
import { Alert, Box, Button, CircularProgress, Container, Typography } from '@mui/material'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../features/auth/model/authContext'

const AppShell = lazy(() => import('../shared/layout/AppShell').then(m => ({ default: m.AppShell })))

export function PasswordRoute() {
  const { state, notice, logout } = useAuth()
  if (state.status === 'authenticated') return <AppShell />
  if (state.status === 'passwordChangeRequired') return <Container component="main" maxWidth="sm" sx={{ py: 5 }}>
    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 3 }}>
      <Button onClick={() => { void logout() }}>Cerrar sesión</Button>
    </Box>
    {notice && <Alert severity={notice.severity} sx={{ mb: 2 }}>{notice.message}</Alert>}
    <Outlet />
  </Container>
  if (state.status === 'closing' || state.status === 'validating' || state.status === 'authenticating') {
    return <Box role="status" sx={{ p: 5 }}><CircularProgress size={24} /><Typography>Validando sesión…</Typography></Box>
  }
  return <Navigate to="/login" replace />
}
