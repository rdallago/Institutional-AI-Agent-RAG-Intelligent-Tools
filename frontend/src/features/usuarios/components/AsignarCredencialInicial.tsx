import { useState } from 'react'
import { Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material'
import { useForm, useWatch } from 'react-hook-form'
import type { UsuarioRespuesta } from '../../../api/contracts'
import { useAuth } from '../../auth/model/authContext'
import { NewPasswordFields } from '../../../shared/ui/NewPasswordFields'
import { validateConfirmation, validateNewPassword } from '../../../shared/validation/passwordPolicy'
import { createUsuariosApi } from '../api/usuariosApi'
import { ambiguousMutation, mutationMessage } from '../api/mutationErrors'
import { useMutation } from '../hooks/useMutation'

function AssignmentDialog({ user, close, completed }: { user: UsuarioRespuesta; close: () => void; completed: () => void }) {
  const { get, mutate } = useAuth()
  const action = useMutation()
  const { register, control, handleSubmit, getValues, reset, formState: { errors, isSubmitting } } = useForm<{
    password_inicial: string; confirmacion: string
  }>({ defaultValues: { password_inicial: '', confirmacion: '' } })
  const [initial, confirmation] = useWatch({ control, name: ['password_inicial', 'confirmacion'] })
  const busy = action.busy || isSubmitting
  return <Dialog open onClose={() => { if (!busy) close() }} aria-labelledby="assign-initial-title" fullWidth maxWidth="sm">
    <Box component="form" noValidate onSubmit={event => { void handleSubmit(async input => {
      reset()
      await action.run(signal => createUsuariosApi(get, mutate).asignarInicial(user.id, input.password_inicial, signal), completed)
    })(event) }}>
      <DialogTitle id="assign-initial-title">Asignar contraseña inicial</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <Typography>{user.nombre} {user.apellido} · {user.email}</Typography>
          <Alert severity="info">Solo para perfiles que aún no tienen credencial. El servidor comprobará esta condición. No reemplaza ni restablece contraseñas existentes. El usuario deberá cambiar la inicial al ingresar.</Alert>
          <Typography variant="body2">La disponibilidad del aprovisionamiento depende de la habilitación del servidor.</Typography>
          {action.error != null && <Alert severity="error">{ambiguousMutation(action.error)
            ? 'No se pudo confirmar la asignación. Puede haberse aplicado. No repitas el envío automáticamente; el perfil no informa si tiene credencial. Consultá con el administrador antes de reintentar.'
            : mutationMessage(action.error)}</Alert>}
          <NewPasswordFields id="assign-initial" label="Contraseña inicial" confirmationLabel="Confirmar contraseña inicial"
            value={initial} confirmation={confirmation} disabled={busy}
            passwordField={register('password_inicial', { validate: validateNewPassword, deps: ['confirmacion'] })}
            confirmationField={register('confirmacion', { validate: value => validateConfirmation(value, getValues('password_inicial')) })}
            error={errors.password_inicial?.message} confirmationError={errors.confirmacion?.message} />
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button autoFocus disabled={busy} onClick={close}>Cancelar</Button>
        <Button type="submit" variant="contained" disabled={busy || ambiguousMutation(action.error)}>{busy ? 'Asignando…' : 'Confirmar asignación'}</Button>
      </DialogActions>
    </Box>
  </Dialog>
}

export function AsignarCredencialInicial({ user }: { user: UsuarioRespuesta }) {
  const [open, setOpen] = useState(false)
  const [success, setSuccess] = useState(false)
  return <Stack spacing={1} sx={{ mt: 3 }}>
    {success && <Alert severity="success">Contraseña inicial asignada. El usuario deberá cambiarla al ingresar.</Alert>}
    <Typography variant="body2">La asignación inicial solo sirve para perfiles sin credencial; no permite restablecer contraseñas.</Typography>
    {!user.activo && <Typography variant="body2">El perfil debe estar activo para asignar una contraseña inicial.</Typography>}
    <Box><Button variant="outlined" disabled={!user.activo} onClick={() => { setSuccess(false); setOpen(true) }}>Asignar contraseña inicial</Button></Box>
    {open && <AssignmentDialog user={user} close={() => setOpen(false)} completed={() => { setOpen(false); setSuccess(true) }} />}
  </Stack>
}
