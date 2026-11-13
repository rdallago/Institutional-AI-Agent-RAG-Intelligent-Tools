import { List, ListItem, Typography } from '@mui/material'
import type { UseFormRegisterReturn } from 'react-hook-form'
import { passwordConditions } from '../validation/passwordPolicy'
import { PasswordField } from './PasswordField'

interface Props {
  id: string
  label?: string
  confirmationLabel?: string
  value: string
  confirmation: string
  passwordField: UseFormRegisterReturn
  confirmationField: UseFormRegisterReturn
  error?: string
  confirmationError?: string
  disabled: boolean
}

export function NewPasswordFields({ id, label = 'Contraseña nueva', confirmationLabel = 'Confirmar contraseña nueva',
  value, confirmation, passwordField, confirmationField, error, confirmationError, disabled }: Props) {
  const conditions = passwordConditions(value)
  const checks = [
    ['Entre 15 y 128 caracteres Unicode', conditions.length],
    ['Hasta 512 bytes UTF-8', conditions.bytes],
    ['Caracteres Unicode válidos', conditions.unicode],
    ['Confirmación idéntica', value.length > 0 && value === confirmation],
  ] as const
  return <>
    <Typography id={`${id}-policy`} variant="body2">Se admiten espacios y Unicode, sin exigir mayúsculas, números ni símbolos. El servidor también verifica contraseñas comunes.</Typography>
    <List dense aria-label="Requisitos de contraseña" sx={{ py: 0 }}>
      {checks.map(([text, valid]) => <ListItem key={text} sx={{ px: 0, py: 0.25, color: valid ? 'success.main' : 'text.secondary' }}>
        <Typography variant="body2">{valid ? '✓ Cumplido' : '○ Pendiente'}: {text}</Typography>
      </ListItem>)}
    </List>
    <PasswordField id={`${id}-new`} label={label} disabled={disabled} autoComplete="new-password"
      {...passwordField} error={!!error} helperText={error} slotProps={{ htmlInput: { 'aria-describedby': `${id}-policy${error ? ` ${id}-new-helper-text` : ''}` } }} />
    <PasswordField id={`${id}-confirm`} label={confirmationLabel} disabled={disabled} autoComplete="new-password"
      {...confirmationField} error={!!confirmationError} helperText={confirmationError} />
  </>
}
