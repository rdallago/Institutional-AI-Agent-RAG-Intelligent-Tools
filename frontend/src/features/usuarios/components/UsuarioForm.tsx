import { useEffect } from 'react'
import { Alert, Box, Button, MenuItem, Stack, TextField, Typography } from '@mui/material'
import { Link } from 'react-router-dom'
import { useForm, useWatch } from 'react-hook-form'
import type { UsuarioRespuesta } from '../../../api/contracts'
import { ApiError } from '../../../api/errors'
import { validateEmail, validateName } from '../../../shared/validation/profileFields'
import type { CrearPerfilDatos } from '../api/usuariosApi'
import { MutationError } from './MutationError'
import { ambiguousMutation } from '../api/mutationErrors'
import { NewPasswordFields } from '../../../shared/ui/NewPasswordFields'
import { validateConfirmation, validateNewPassword } from '../../../shared/validation/passwordPolicy'

interface Props {
  user?: UsuarioRespuesta
  busy: boolean
  error: unknown
  search: string
  submit: (data: CrearPerfilDatos) => Promise<void>
}
export function UsuarioForm({ user, busy, error, search, submit }: Props) {
  const { register, control, getValues, resetField, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<CrearPerfilDatos & { confirmacion: string }>({
    defaultValues: { nombre: user?.nombre ?? '', apellido: user?.apellido ?? '', email: user?.email ?? '', rol: user?.rol ?? 'USUARIO', password_inicial: '', confirmacion: '' },
  })
  const [initial, confirmation] = useWatch({ control, name: ['password_inicial', 'confirmacion'] })
  useEffect(() => {
    if (!(error instanceof ApiError)) return
    const fields = [...error.fields]
    if (error.code === 'EMAIL_EN_USO' || error.code === 'USUARIO_ACTIVO_EXISTENTE' || error.code === 'USUARIO_INACTIVO_REACTIVABLE') fields.push('email')
    for (const field of fields) {
      if (field === 'nombre' || field === 'apellido' || field === 'email' || (field === 'rol' && !user)) {
        setError(field, { type: 'server', message: 'Revisá este campo. El servidor rechazó su valor.' })
      }
    }
    if (!user && error.code === 'PASSWORD_INVALIDA') setError('password_inicial', { message: 'El servidor rechazó la contraseña inicial. Revisá la política y elegí otra.' })
  }, [error, setError, user])
  const locked = busy || isSubmitting
  return <Box component="form" noValidate aria-busy={locked} onSubmit={event => { void handleSubmit(async data => {
    const payload = { nombre: data.nombre, apellido: data.apellido, email: data.email, rol: data.rol, password_inicial: data.password_inicial }
    if (!user) { resetField('password_inicial'); resetField('confirmacion') }
    await submit(payload)
  })(event) }}>
    <Stack spacing={2.5}>
      {!user && <Alert severity="info">El administrador establece una contraseña inicial. El usuario deberá cambiarla antes de acceder a la aplicación. La disponibilidad del aprovisionamiento depende de la habilitación del servidor.</Alert>}
      {user && <Typography color="text.secondary">Rol: {user.rol}. Estado: {user.activo ? 'Activo' : 'Inactivo'}. Solo se modifican nombre, apellido y email.</Typography>}
      <MutationError error={error} search={search} />
      <TextField label="Nombre" id="perfil-nombre" disabled={locked} {...register('nombre', { validate: validateName })} error={!!errors.nombre} helperText={errors.nombre?.message} autoComplete="given-name" />
      <TextField label="Apellido" id="perfil-apellido" disabled={locked} {...register('apellido', { validate: validateName })} error={!!errors.apellido} helperText={errors.apellido?.message} autoComplete="family-name" />
      <TextField label="Email" id="perfil-email" disabled={locked} {...register('email', { validate: validateEmail })} error={!!errors.email} helperText={errors.email?.message}
        autoComplete="email" slotProps={{ htmlInput: { inputMode: 'email', autoCapitalize: 'none', spellCheck: false } }} />
      {!user && <TextField select label="Rol" id="perfil-rol" disabled={locked} defaultValue="USUARIO" {...register('rol', { validate: value => value === 'ADMIN' || value === 'USUARIO' || 'El rol debe ser ADMIN o USUARIO.' })} error={!!errors.rol} helperText={errors.rol?.message}>
        <MenuItem value="USUARIO">USUARIO</MenuItem><MenuItem value="ADMIN">ADMIN</MenuItem>
      </TextField>}
      {!user && <NewPasswordFields id="perfil-initial" label="Contraseña inicial" confirmationLabel="Confirmar contraseña inicial"
        value={initial} confirmation={confirmation} disabled={locked}
        passwordField={register('password_inicial', { validate: validateNewPassword, deps: ['confirmacion'] })}
        confirmationField={register('confirmacion', { validate: value => validateConfirmation(value, getValues('password_inicial')) })}
        error={errors.password_inicial?.message} confirmationError={errors.confirmacion?.message} />}
      <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
        <Button type="submit" variant="contained" disabled={locked || ambiguousMutation(error)}>{locked ? 'Guardando…' : user ? 'Guardar cambios' : 'Crear perfil'}</Button>
        <Button component={Link} to={user ? `/usuarios/${user.id}?${search}` : `/usuarios?${search}`} disabled={locked}>Cancelar</Button>
      </Stack>
    </Stack>
  </Box>
}
