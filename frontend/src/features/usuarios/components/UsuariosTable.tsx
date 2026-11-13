import { Box, Button, Chip, Paper, Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import type { UsuarioRespuesta } from '../../../api/contracts'

export function UsuariosTable({ users, search }: { users: UsuarioRespuesta[]; search: string }) {
  const detail = (user: UsuarioRespuesta) => <Button component={Link} to={`/usuarios/${user.id}?${search}`} aria-label={`Ver perfil de ${user.nombre} ${user.apellido}`}>Ver perfil</Button>
  const status = (user: UsuarioRespuesta) => <Chip size="small" label={user.activo ? 'Activo' : 'Inactivo'} variant="outlined" color={user.activo ? 'primary' : 'default'} />
  return <>
    <TableContainer component={Paper} variant="outlined" sx={{ display: { xs: 'none', md: 'block' }, borderRadius: 3 }}>
      <Table aria-label="Perfiles de usuarios">
        <TableHead><TableRow>{['Nombre', 'Apellido', 'Email', 'Rol', 'Estado', 'Detalle'].map(label => <TableCell key={label}>{label}</TableCell>)}</TableRow></TableHead>
        <TableBody>{users.map(user => <TableRow key={user.id}>
          <TableCell>{user.nombre}</TableCell><TableCell>{user.apellido}</TableCell>
          <TableCell sx={{ overflowWrap: 'anywhere' }}>{user.email}</TableCell><TableCell>{user.rol}</TableCell>
          <TableCell>{status(user)}</TableCell><TableCell>{detail(user)}</TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </TableContainer>
    <Stack spacing={2} sx={{ display: { xs: 'flex', md: 'none' } }}>
      {users.map(user => <Paper component="article" variant="outlined" key={user.id} sx={{ p: 2, borderRadius: 3 }}>
        <Box component="dl" sx={{ m: 0 }}>
          {([['Nombre', user.nombre], ['Apellido', user.apellido], ['Email', user.email], ['Rol', user.rol]]).map(([label, value]) => <Box key={label} sx={{ mb: 1 }}>
            <Typography component="dt" variant="caption" color="text.secondary">{label}</Typography>
            <Typography component="dd" sx={{ m: 0, overflowWrap: 'anywhere' }}>{value}</Typography>
          </Box>)}
          <Typography component="dt" variant="caption" color="text.secondary">Estado</Typography>
          <Box component="dd" sx={{ m: 0 }}>{status(user)}</Box>
        </Box>
        {detail(user)}
      </Paper>)}
    </Stack>
  </>
}
