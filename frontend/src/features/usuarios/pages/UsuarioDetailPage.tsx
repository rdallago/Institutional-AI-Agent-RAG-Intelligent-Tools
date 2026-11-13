import { useCallback, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Paper, Typography } from '@mui/material'
import { Link, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/model/authContext'
import { consultaSearch, createUsuariosApi, parseConsulta } from '../api/usuariosApi'
import { useConsulta } from '../hooks/useConsulta'
import { ConsultaError } from '../components/ConsultaError'
import { UsuarioActions } from '../components/UsuarioActions'
import { AsignarCredencialInicial } from '../components/AsignarCredencialInicial'

function Detail({ id, search }: { id: string; search: string }) {
  const location = useLocation()
  const [success, setSuccess] = useState<string>(() => {
    const message: unknown = location.state?.profileSuccess
    return message === 'Perfil creado correctamente.' || message === 'Perfil actualizado correctamente.' ? message : ''
  })
  const { get } = useAuth()
  const load = useCallback((signal: AbortSignal) => createUsuariosApi(get).obtener(id, signal), [get, id])
  const { result, retry } = useConsulta(id, load)
  const user = result.status === 'success' ? result.data : null
  return <section>
    <Button component={Link} to={`/usuarios?${search}`} sx={{ mb: 2 }}>Volver al listado</Button>
    <Typography component="h1" variant="h3" sx={{ mb: 3 }}>Detalle de perfil</Typography>
    {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
    {result.status === 'loading' && <Box role="status"><CircularProgress size={24} /><Typography>Cargando perfil…</Typography></Box>}
    {result.status === 'error' && <ConsultaError error={result.error} retry={retry} />}
    {user && <Paper variant="outlined" sx={{ p: 3, borderRadius: 3 }}>
      <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 3, m: 0 }}>
        {[
          ['Nombre', user.nombre], ['Apellido', user.apellido], ['Email', user.email], ['Rol', user.rol],
          ['Estado', user.activo ? 'Activo' : 'Inactivo'], ['UUID', user.id],
          ['Fecha de creación', new Intl.DateTimeFormat('es-AR', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(user.fecha_creacion))],
        ].map(([label, value]) => <Box key={label}>
          <Typography component="dt" color="text.secondary" variant="body2">{label}</Typography>
          <Typography component="dd" sx={{ m: 0, overflowWrap: 'anywhere' }}>{value}</Typography>
        </Box>)}
      </Box>
      <UsuarioActions key={`${user.id}-${user.activo}`} user={user} search={search} updated={message => { setSuccess(message); retry() }} />
      <AsignarCredencialInicial key={`initial-${user.id}-${user.activo}`} user={user} />
    </Paper>}
  </section>
}
export default function UsuarioDetailPage() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  return <Detail key={id} id={id} search={consultaSearch(parseConsulta(params))} />
}
