import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material'
import { useForm, useWatch } from 'react-hook-form'
import { ApiError } from '../../../api/errors'
import { PasswordField } from '../../../shared/ui/PasswordField'
import { NewPasswordFields } from '../../../shared/ui/NewPasswordFields'
import { validateConfirmation, validateNewPassword } from '../../../shared/validation/passwordPolicy'
import { useAuth } from '../model/authContext'

interface Fields { password_actual: string; password_nueva: string; confirmacion: string }

export default function ChangePasswordPage() {
  const { state, changePassword } = useAuth()
  const mandatory = state.status === 'passwordChangeRequired'
  const { register, control, handleSubmit, getValues, reset, setError, formState: { errors } } = useForm<Fields>({
    defaultValues: { password_actual: '', password_nueva: '', confirmacion: '' }, mode: 'onChange',
  })
  const [value, confirmation] = useWatch({ control, name: ['password_nueva', 'confirmacion'] })
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [remaining, setRemaining] = useState(0)
  const deadline = useRef(0)
  const locked = useRef(false)
  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    document.title = 'Cambiar contraseña · Espacio de trabajo'
    const timer = setInterval(() => setRemaining(Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000))), 500)
    return () => { alive.current = false; clearInterval(timer) }
  }, [])
  const submit = useCallback(async (data: Fields) => {
    if (locked.current || Date.now() < deadline.current) return
    locked.current = true
    setBusy(true)
    setMessage('')
    const request = changePassword({ password_actual: data.password_actual, password_nueva: data.password_nueva })
    // No retener secretos en el formulario mientras se procesa o tras un error.
    reset()
    try { await request } catch (error) {
      if (!alive.current || (error instanceof ApiError && error.kind === 'cancelled')) return
      if (error instanceof ApiError && error.code === 'CREDENCIALES_INVALIDAS') {
        setError('password_actual', { message: 'La contraseña actual es incorrecta.' })
      } else if (error instanceof ApiError && error.status === 429) {
        const wait = Math.max(1, error.retryAfter ?? 60)
        deadline.current = Date.now() + wait * 1000
        setRemaining(wait)
        setMessage('Demasiados intentos. Esperá antes de volver a intentar.')
      } else {
        setMessage(error instanceof ApiError && error.code === 'PASSWORD_REUTILIZADA'
          ? 'Elegí una contraseña diferente de la actual y de la inicial.'
          : error instanceof ApiError && error.status === 422
            ? 'El servidor rechazó la nueva contraseña. Revisá la política y elegí otra.'
            : 'No se pudo completar el cambio de contraseña.')
      }
    } finally { locked.current = false; if (alive.current) setBusy(false) }
  }, [changePassword, reset, setError])
  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 3 }}>Cambiar contraseña</Typography>
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 }, borderRadius: 3, maxWidth: 720 }}>
      <Box component="form" noValidate aria-busy={busy} onSubmit={event => { void handleSubmit(submit)(event) }}>
        <Stack spacing={2.5}>
          <Alert severity="info">{mandatory ? 'Debés cambiar tu contraseña inicial antes de acceder a la aplicación.' : 'El cambio revoca todas tus sesiones. Tendrás que ingresar nuevamente.'}</Alert>
          {message && <Alert severity="error">{message}</Alert>}
          <PasswordField label="Contraseña actual" id="password-current" autoComplete="current-password" disabled={busy}
            {...register('password_actual', { required: 'Ingresá tu contraseña actual.' })}
            error={!!errors.password_actual} helperText={errors.password_actual?.message} />
          <NewPasswordFields id="password-change" value={value} confirmation={confirmation} disabled={busy || remaining > 0}
            passwordField={register('password_nueva', { validate: validateNewPassword, deps: ['confirmacion'] })}
            confirmationField={register('confirmacion', { validate: current => validateConfirmation(current, getValues('password_nueva')) })}
            error={errors.password_nueva?.message} confirmationError={errors.confirmacion?.message} />
          {remaining > 0 && <Typography role="status">Podés volver a intentar en {remaining} segundos.</Typography>}
          <Button type="submit" variant="contained" disabled={busy || remaining > 0 || validateNewPassword(value) !== true || validateConfirmation(confirmation, value) !== true}>
            {busy ? 'Cambiando contraseña…' : 'Guardar nueva contraseña'}
          </Button>
        </Stack>
      </Box>
    </Paper>
  </section>
}
