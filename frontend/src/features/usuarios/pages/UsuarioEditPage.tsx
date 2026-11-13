import { useCallback } from 'react'
import { Box, CircularProgress, Paper, Typography } from '@mui/material'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/model/authContext'
import { consultaSearch, createUsuariosApi, parseConsulta } from '../api/usuariosApi'
import { useConsulta } from '../hooks/useConsulta'
import { useMutation } from '../hooks/useMutation'
import { UsuarioForm } from '../components/UsuarioForm'
import { ConsultaError } from '../components/ConsultaError'

function Edit({ id, search }: { id: string; search: string }) {
  const { get, mutate, state, refreshProfile } = useAuth()
  const navigate = useNavigate()
  const load = useCallback((signal: AbortSignal) => createUsuariosApi(get).obtener(id, signal), [get, id])
  const { result, retry } = useConsulta(id, load)
  const action = useMutation()
  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 3 }}>Editar perfil</Typography>
    {result.status === 'loading' && <Box role="status"><CircularProgress size={24} /> Cargando perfil…</Box>}
    {result.status === 'error' && <ConsultaError error={result.error} retry={retry} />}
    {result.status === 'success' && <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 }, borderRadius: 3, maxWidth: 720 }}>
      <UsuarioForm user={result.data} busy={action.busy} error={action.error} search={search}
        submit={data => action.run(signal => createUsuariosApi(get, mutate).editar(id, data, signal), () => {
          navigate(`/usuarios/${id}?${search}`, { replace: true, state: { profileSuccess: 'Perfil actualizado correctamente.' } })
          if (state.status === 'authenticated' && state.user.id.toLowerCase() === id.toLowerCase()) void refreshProfile()
        }).then(() => {})} />
    </Paper>}
  </section>
}
export default function UsuarioEditPage() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  return <Edit key={id} id={id} search={consultaSearch(parseConsulta(params))} />
}
