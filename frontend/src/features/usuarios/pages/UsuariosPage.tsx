import { useCallback } from 'react'
import { Box, Button, CircularProgress, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/model/authContext'
import { consultaSearch, createUsuariosApi, parseConsulta } from '../api/usuariosApi'
import { useConsulta } from '../hooks/useConsulta'
import { ConsultaError } from '../components/ConsultaError'
import { UsuariosTable } from '../components/UsuariosTable'

export default function UsuariosPage() {
  const { get } = useAuth()
  const [params, setParams] = useSearchParams()
  const query = parseConsulta(params)
  const { estado, limite, desplazamiento } = query
  const search = consultaSearch(query)
  const load = useCallback((signal: AbortSignal) => createUsuariosApi(get).listar({ estado, limite, desplazamiento }, signal), [get, estado, limite, desplazamiento])
  const { result, retry } = useConsulta(search, load)
  const change = (next: Partial<typeof query>) => setParams(consultaSearch({ ...query, ...next }))
  const previous = () => change({ desplazamiento: Math.max(0, desplazamiento - limite) })
  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 1 }}>Administración de usuarios</Typography>
    <Typography color="text.secondary" sx={{ mb: 3 }}>Consultá los perfiles y filtrá por su estado. Los más antiguos aparecen primero.</Typography>
    <Button component={Link} to={`/usuarios/nuevo?${search}`} variant="contained" sx={{ mb: 3 }}>Crear perfil</Button>
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} sx={{ mb: 3 }}>
      <TextField select label="Estado" value={estado} onChange={e => change({ estado: e.target.value as typeof estado, desplazamiento: 0 })} sx={{ minWidth: 180 }}>
        <MenuItem value="activos">Activos</MenuItem><MenuItem value="inactivos">Inactivos</MenuItem><MenuItem value="todos">Todos</MenuItem>
      </TextField>
      <TextField select label="Perfiles por página" value={limite} onChange={e => change({ limite: Number(e.target.value), desplazamiento: 0 })} sx={{ minWidth: 180 }}>
        {[...new Set([10, 20, 50, 100, limite])].sort((a, b) => a - b).map(size => <MenuItem key={size} value={size}>{size}</MenuItem>)}
      </TextField>
    </Stack>
    <Box aria-busy={result.status === 'loading'}>
      {result.status === 'loading' && <Stack direction="row" spacing={2} role="status"><CircularProgress size={24} /><Typography>Cargando perfiles…</Typography></Stack>}
      {result.status === 'error' && <ConsultaError error={result.error} retry={retry} />}
      {result.status === 'success' && (result.data.length > 0
        ? <UsuariosTable users={result.data} search={search} />
        : <Typography role="status">No hay perfiles en esta página para el estado seleccionado.</Typography>)}
    </Box>
    <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 3, flexWrap: 'wrap', gap: 1 }}>
      <Button onClick={previous} disabled={desplazamiento === 0}>Anterior</Button>
      <Typography variant="body2">{result.status === 'success'
        ? result.data.length ? `Perfiles ${desplazamiento + 1}–${desplazamiento + result.data.length}` : 'Página sin resultados'
        : `Desde el perfil ${desplazamiento + 1}`}</Typography>
      <Button disabled={result.status !== 'success' || result.data.length < limite || desplazamiento > Number.MAX_SAFE_INTEGER - limite - 100}
        onClick={() => change({ desplazamiento: desplazamiento + limite })}>Siguiente</Button>
    </Stack>
    <Typography variant="caption" color="text.secondary" component="p">Navegación sin total de perfiles. Una página completa permite avanzar, aunque la siguiente puede estar vacía.</Typography>
  </section>
}
