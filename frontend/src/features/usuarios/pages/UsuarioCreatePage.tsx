import { Paper, Typography } from '@mui/material'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../auth/model/authContext'
import { consultaSearch, createUsuariosApi, parseConsulta } from '../api/usuariosApi'
import { useMutation } from '../hooks/useMutation'
import { UsuarioForm } from '../components/UsuarioForm'

export default function UsuarioCreatePage() {
  const { get, mutate } = useAuth()
  const [params] = useSearchParams()
  const search = consultaSearch(parseConsulta(params))
  const navigate = useNavigate()
  const action = useMutation()
  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 3 }}>Crear perfil</Typography>
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 }, borderRadius: 3, maxWidth: 720 }}>
      <UsuarioForm busy={action.busy} error={action.error} search={search}
        submit={data => action.run(signal => createUsuariosApi(get, mutate).crear(data, signal), user => {
          navigate(`/usuarios/${user.id}?${search}`, { replace: true, state: { profileSuccess: 'Perfil creado correctamente.' } })
        }).then(() => {})} />
    </Paper>
  </section>
}
