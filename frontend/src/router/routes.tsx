import { lazy, Suspense } from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'
import { Navigate, Route, Routes } from 'react-router-dom'
import { LoginPage } from '../features/auth/pages/LoginPage'
import { useAuth } from '../features/auth/model/authContext'
import { ProtectedRoute } from './ProtectedRoute'
import { AdminRoute } from './AdminRoute'
import { PasswordRoute } from './PasswordRoute'

const DashboardPage = lazy(() => import('../features/dashboard/pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const MiPerfilPage = lazy(() => import('../features/perfil/pages/MiPerfilPage'))
const AppShell = lazy(() => import('../shared/layout/AppShell').then(m => ({ default: m.AppShell })))
const UsuariosPage = lazy(() => import('../features/usuarios/pages/UsuariosPage'))
const UsuarioDetailPage = lazy(() => import('../features/usuarios/pages/UsuarioDetailPage'))
const UsuarioCreatePage = lazy(() => import('../features/usuarios/pages/UsuarioCreatePage'))
const UsuarioEditPage = lazy(() => import('../features/usuarios/pages/UsuarioEditPage'))
const ChangePasswordPage = lazy(() => import('../features/auth/pages/ChangePasswordPage'))
const ConsultaIAPage = lazy(() => import('../features/ia/pages/ConsultaIAPage'))

export function AppRoutes() {
  const { state } = useAuth()
  return <Suspense fallback={<Box role="status" sx={{ p: 4 }}><CircularProgress size={24} /><Typography>Cargando pantalla…</Typography></Box>}>
    <Routes>
      <Route path="/login" element={state.status === 'passwordChangeRequired' ? <Navigate to="/cambiar-password" replace />
        : state.status === 'authenticated' ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route element={<PasswordRoute />}>
        <Route path="/cambiar-password" element={<ChangePasswordPage />} />
      </Route>
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/mi-perfil" element={<MiPerfilPage />} />
          <Route path="/ia" element={<ConsultaIAPage />} />
          <Route element={<AdminRoute />}>
            <Route path="/usuarios" element={<UsuariosPage />} />
            <Route path="/usuarios/nuevo" element={<UsuarioCreatePage />} />
            <Route path="/usuarios/:id" element={<UsuarioDetailPage />} />
            <Route path="/usuarios/:id/editar" element={<UsuarioEditPage />} />
          </Route>
          <Route path="*" element={<Typography component="h1" variant="h4">Página no encontrada</Typography>} />
        </Route>
      </Route>
    </Routes>
  </Suspense>
}
