import { Box, Button, Chip, Paper, Typography } from '@mui/material'
import { useAuth } from '../../auth/model/authContext'

export default function MiPerfilPage() {
  const { state, refreshProfile } = useAuth()
  if (state.status !== 'authenticated') return null
  const user = state.user
  const fields = [
    ['Nombre', user.nombre], ['Apellido', user.apellido], ['Email', user.email],
    ['Rol', user.rol], ['Estado', user.activo ? 'Activo' : 'Inactivo'],
    ['Fecha de creación', new Intl.DateTimeFormat('es-AR', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(user.fecha_creacion))],
  ]
  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 1 }}>Mi perfil</Typography>
    <Typography color="text.secondary" sx={{ mb: 3 }}>Datos de tu cuenta verificados por el servidor. Esta pantalla es de consulta.</Typography>
    <Paper variant="outlined" sx={{ p: { xs: 3, md: 4 }, borderRadius: 4 }}>
      <Chip label={user.rol} color="primary" variant="outlined" sx={{ mb: 3 }} />
      <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 3, m: 0 }}>
        {fields.map(([label, value]) => <Box key={label}>
          <Typography component="dt" color="text.secondary" variant="body2">{label}</Typography>
          <Typography component="dd" sx={{ m: 0, mt: .5, overflowWrap: 'anywhere' }}>{value}</Typography>
        </Box>)}
      </Box>
      <Button sx={{ mt: 3 }} onClick={() => { void refreshProfile() }}>Actualizar perfil</Button>
    </Paper>
  </section>
}
