import { Alert, Box, Chip, Container, Paper, Stack, Typography } from '@mui/material'
import { LoginForm } from '../components/LoginForm'
import { useAuth } from '../model/authContext'

export function LoginPage() {
  const { notice, state } = useAuth()
  return <Box component="main" sx={{ minHeight: '100dvh', display: 'grid', alignItems: 'center', py: 5 }}>
    <Container maxWidth="lg">
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: { xs: 4, md: 10 }, alignItems: 'center' }}>
        <Stack spacing={3} sx={{ maxWidth: 490 }}>
          <Typography variant="overline" sx={{ color: 'primary.main', fontWeight: 800, letterSpacing: '.18em' }}>USUARIOS / ESPACIO DE TRABAJO</Typography>
          <Typography component="h1" variant="h2">Todo empieza con una conexión segura.</Typography>
          <Typography color="text.secondary" sx={{ fontSize: '1.1rem', maxWidth: 400 }}>Accedé a tu espacio y consultá la información de tu cuenta.</Typography>
          <Box><Chip label="Acceso personal" variant="outlined" size="small" /></Box>
        </Stack>
        <Paper component="section" aria-labelledby="login-title" elevation={0} sx={{ p: { xs: 3, sm: 5 }, border: '1px solid', borderColor: 'divider', borderRadius: 4 }}>
          <Typography variant="overline" color="text.secondary">BIENVENIDO</Typography>
          <Typography component="h2" variant="h4" id="login-title" sx={{ mt: 1, mb: 1 }}>Ingresá a tu cuenta</Typography>
          <Typography color="text.secondary" sx={{ mb: 4 }}>Usá tu email y contraseña para continuar.</Typography>
          {notice && <Alert severity={notice.severity} sx={{ mb: 3 }}>{notice.message}</Alert>}
          {state.status === 'closing' ? <Typography role="status">Cerrando sesión…</Typography> : <LoginForm />}
          <Typography variant="caption" color="text.secondary" component="p" sx={{ mt: 3, mb: 0 }}>Al recargar o cerrar esta página, tendrás que ingresar nuevamente.</Typography>
        </Paper>
      </Box>
    </Container>
  </Box>
}
