import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Stack, TextField, Typography } from '@mui/material'
import { useForm } from 'react-hook-form'
import type { LoginSolicitud } from '../../../api/contracts'
import { ApiError, loginErrorMessage } from '../../../api/errors'
import { PasswordField } from '../../../shared/ui/PasswordField'
import { useAuth } from '../model/authContext'

export function LoginForm() {
  const { state, login } = useAuth()
  const { register, handleSubmit, resetField, formState: { errors, isSubmitting } } = useForm<LoginSolicitud>({
    defaultValues: { email: '', password: '' },
  })
  const [message, setMessage] = useState('')
  const [remaining, setRemaining] = useState(0)
  const alive = useRef(true)
  const locked = useRef(false)
  const deadline = useRef(0)
  useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
  useEffect(() => {
    const timer = window.setInterval(() => {
      setRemaining(Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000)))
    }, 500)
    return () => window.clearInterval(timer)
  }, [])
  const busy = isSubmitting || state.status === 'authenticating' || state.status === 'validating'
  const submit = useCallback(async (input: LoginSolicitud) => {
    if (locked.current || Date.now() < deadline.current) return
    locked.current = true
    setMessage('')
    try { await login(input) } catch (error) {
      if (!alive.current || (error instanceof ApiError && error.kind === 'cancelled')) return
      setMessage(loginErrorMessage(error))
      if (error instanceof ApiError && error.status === 429) {
        // A missing/invalid header gets a conservative UI delay; backend stays authoritative.
        const wait = Math.max(1, error.retryAfter ?? 60)
        deadline.current = Date.now() + wait * 1000
        setRemaining(wait)
      }
    } finally {
      locked.current = false
      if (alive.current) resetField('password')
    }
  }, [login, resetField])
  return <Box component="form" noValidate onSubmit={event => { void handleSubmit(submit)(event) }} aria-busy={busy}>
    <Stack spacing={2.5}>
      {message && <Alert severity="error" role="alert">{message}</Alert>}
      <TextField label="Email" id="login-email" fullWidth autoComplete="username" disabled={busy}
        {...register('email', { validate: value => value.trim().length > 0 || 'Ingresá tu email.' })}
        error={!!errors.email} helperText={errors.email?.message}
        slotProps={{ htmlInput: { inputMode: 'email', autoCapitalize: 'none', spellCheck: false } }} />
      <PasswordField label="Contraseña" id="login-password" fullWidth autoComplete="current-password" disabled={busy}
        {...register('password', {
          required: 'Ingresá tu contraseña.',
          validate: value => [...value].length <= 128 || 'La contraseña admite hasta 128 caracteres.',
        })} error={!!errors.password} helperText={errors.password?.message} />
      {remaining > 0 && <Typography variant="body2" role="status">Podés volver a intentar en {remaining} segundos.</Typography>}
      <Button type="submit" variant="contained" size="large" fullWidth disabled={busy || remaining > 0}
        startIcon={busy ? <CircularProgress size={18} color="inherit" aria-hidden="true" /> : undefined}>
        {state.status === 'validating' ? 'Verificando perfil…' : busy ? 'Ingresando…' : 'Ingresar'}
      </Button>
    </Stack>
  </Box>
}
