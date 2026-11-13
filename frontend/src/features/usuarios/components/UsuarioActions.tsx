import { useState } from 'react'
import { Button, Stack, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import type { UsuarioRespuesta } from '../../../api/contracts'
import { useAuth } from '../../auth/model/authContext'
import { createUsuariosApi } from '../api/usuariosApi'
import { useMutation } from '../hooks/useMutation'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { MutationError } from './MutationError'
import { ambiguousMutation } from '../api/mutationErrors'

export function UsuarioActions({ user, search, updated }: { user: UsuarioRespuesta; search: string; updated: (message: string) => void }) {
  const { get, mutate, state } = useAuth()
  const [confirm, setConfirm] = useState(false)
  const action = useMutation()
  if (state.status !== 'authenticated' || state.user.rol !== 'ADMIN') return null
  const self = user.id.toLowerCase() === state.user.id.toLowerCase()
  const label = user.activo ? 'Dar de baja' : 'Reactivar'
  const apply = () => {
    void action.run(async signal => {
      if (user.activo) await createUsuariosApi(get, mutate).baja(user.id, signal)
      else await createUsuariosApi(get, mutate).reactivar(user.id, signal)
    }, () => {
      setConfirm(false)
      updated(user.activo ? 'Baja lógica aplicada. Las sesiones del perfil fueron revocadas.' : 'Perfil reactivado. Las sesiones anteriores siguen revocadas.')
    }).then(outcome => { if (outcome === false) setConfirm(false) })
  }
  return <Stack spacing={2} sx={{ mt: 3 }}>
    <MutationError error={action.error} search={search} />
    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
      <Button component={Link} to={`/usuarios/${user.id}/editar?${search}`} disabled={action.busy}>Editar</Button>
      <Button color={user.activo ? 'error' : 'primary'} variant="outlined" onClick={() => setConfirm(true)}
        disabled={action.busy || ambiguousMutation(action.error) || (user.activo && self)}
        aria-describedby={self && user.activo ? 'self-baja-reason' : undefined}>{label}</Button>
    </Stack>
    {self && user.activo && <Typography id="self-baja-reason" variant="body2" color="text.secondary">No podés dar de baja tu propio perfil administrativo.</Typography>}
    <ConfirmDialog open={confirm} title={`${label}: ${user.nombre} ${user.apellido}`} busy={action.busy}
      description={`${user.email}. ${user.activo
        ? 'La baja es lógica: no elimina físicamente el perfil. Las sesiones existentes de este usuario serán revocadas.'
        : 'La reactivación no restaura sesiones anteriores ni asigna credenciales nuevas.'}`}
      confirm={apply} cancel={() => setConfirm(false)} />
  </Stack>
}
