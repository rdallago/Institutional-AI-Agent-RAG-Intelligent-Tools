import { Box, Container, Divider, Paper, Typography } from '@mui/material'
import { useAuth } from '../../auth/model/authContext'

export function DashboardPage() {
  const { state } = useAuth()
  if (state.status !== 'authenticated') return null
  const { user } = state
  return <Box component="section">
    <Container maxWidth="md" disableGutters>
      <Typography variant="overline" color="primary">USUARIOS / TU ESPACIO</Typography>
      <Typography component="h1" variant="h3" sx={{ mt: 2, mb: 1 }}>Bienvenido, {user.nombre}</Typography>
      <Typography color="text.secondary" sx={{ mb: 4 }}>Tu identidad fue verificada. Esta es la información de tu cuenta.</Typography>
      <Paper elevation={0} sx={{ p: { xs: 3, md: 5 }, borderRadius: 4, border: '1px solid', borderColor: 'divider' }}>
        <Typography component="h2" variant="h5">Mi cuenta</Typography>
        <Divider sx={{ my: 3 }} />
        <Box component="dl" sx={{ m: 0, display: 'grid', gap: 3 }}>
          <Box><Typography component="dt" color="text.secondary" variant="body2">Nombre y apellido</Typography>
            <Typography component="dd" sx={{ m: 0, mt: .5 }}><span>{user.nombre}</span> <span>{user.apellido}</span></Typography></Box>
          <Box><Typography component="dt" color="text.secondary" variant="body2">Email</Typography>
            <Typography component="dd" sx={{ m: 0, mt: .5, overflowWrap: 'anywhere' }}>{user.email}</Typography></Box>
        </Box>
      </Paper>
      <Typography color="text.secondary" variant="body2" sx={{ mt: 3 }}>Por ahora, al recargar la página se solicita un nuevo ingreso.</Typography>
    </Container>
  </Box>
}
