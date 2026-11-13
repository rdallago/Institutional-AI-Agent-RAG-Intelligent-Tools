import { useEffect, useRef, useState } from 'react'
import { Alert, AppBar, Box, Button, Chip, Container, Drawer, IconButton, List, ListItemButton, ListItemText, Stack, Toolbar, Typography } from '@mui/material'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../features/auth/model/authContext'

export function AppShell() {
  const { state, notice, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const content = useRef<HTMLElement>(null)
  useEffect(() => {
    const names: Record<string, string> = { '/dashboard': 'Inicio', '/mi-perfil': 'Mi perfil', '/usuarios': 'Usuarios', '/cambiar-password': 'Cambiar contraseña', '/ia': 'Consultar IA' }
    document.title = `${names[location.pathname] ?? 'Usuarios'} · Espacio de trabajo`
    content.current?.focus()
  }, [location.pathname])
  if (state.status !== 'authenticated') return null
  const links = [
    { to: '/dashboard', label: 'Inicio' }, { to: '/mi-perfil', label: 'Mi perfil' },
    { to: '/ia', label: 'Consultar IA' },
    ...(state.user.rol === 'ADMIN' ? [{ to: '/usuarios', label: 'Administración de usuarios' }] : []),
    { to: '/cambiar-password', label: 'Cambiar contraseña' },
  ]
  const menu = <List aria-label="Secciones">
    {links.map(link => <ListItemButton key={link.to} component={NavLink} to={link.to} onClick={() => setOpen(false)}
      sx={{ borderRadius: 2, mx: 1, '&.active': { bgcolor: 'action.selected', color: 'primary.main' } }}>
      <ListItemText primary={link.label} />
    </ListItemButton>)}
  </List>
  return <Box sx={{ minHeight: '100dvh' }}>
    <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider' }}>
      <Toolbar sx={{ gap: 2, flexWrap: 'wrap', py: 1 }}>
        <IconButton aria-label="Abrir menú de navegación" onClick={() => setOpen(true)} sx={{ display: { md: 'none' } }}>
          <span aria-hidden="true">☰</span>
        </IconButton>
        <Typography fontWeight={800} color="primary" sx={{ letterSpacing: '.1em', flexGrow: 1 }}>USUARIOS</Typography>
        <Stack><Typography variant="body2">{state.user.nombre} {state.user.apellido}</Typography></Stack>
        <Chip size="small" label={state.user.rol} variant="outlined" color="primary" />
        <Button onClick={() => { void logout() }}>Cerrar sesión</Button>
      </Toolbar>
    </AppBar>
    <Box sx={{ display: 'flex' }}>
      <Box component="nav" aria-label="Navegación principal" sx={{ width: 260, flexShrink: 0, display: { xs: 'none', md: 'block' }, pt: 3 }}>{menu}</Box>
      <Drawer open={open} onClose={() => setOpen(false)} slotProps={{ paper: { sx: { width: 280, p: 1 } } }}>
        <Typography sx={{ p: 2 }}>{state.user.nombre} {state.user.apellido}</Typography>
        <Box component="nav" aria-label="Navegación móvil">{menu}</Box>
        <Button onClick={() => setOpen(false)}>Cerrar menú</Button>
      </Drawer>
      <Container component="main" ref={content} tabIndex={-1} maxWidth="lg" sx={{ py: { xs: 3, md: 5 }, minWidth: 0, outline: 'none' }}>
        {notice && <Alert severity={notice.severity} sx={{ mb: 3 }}>{notice.message}</Alert>}
        <Outlet />
      </Container>
    </Box>
  </Box>
}
