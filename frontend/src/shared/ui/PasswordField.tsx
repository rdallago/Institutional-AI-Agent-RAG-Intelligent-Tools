import { useState } from 'react'
import { IconButton, InputAdornment, TextField } from '@mui/material'
import type { TextFieldProps } from '@mui/material'

export function PasswordField(props: TextFieldProps) {
  const [visible, setVisible] = useState(false)
  return <TextField {...props} type={visible ? 'text' : 'password'} slotProps={{
    ...props.slotProps,
    input: owner => ({ ...(typeof props.slotProps?.input === 'function' ? props.slotProps.input(owner) : props.slotProps?.input), endAdornment: <InputAdornment position="end">
      <IconButton type="button" disabled={props.disabled} aria-label={`${visible ? 'Ocultar' : 'Mostrar'} ${typeof props.label === 'string' ? props.label.toLowerCase() : 'contraseña'}`}
        aria-pressed={visible} onClick={() => setVisible(v => !v)} edge="end" size="small">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" stroke="currentColor" strokeWidth="1.6" />
          <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.6" />
          {visible && <path d="m4 3 16 18" stroke="currentColor" strokeWidth="1.6" />}
        </svg>
      </IconButton>
    </InputAdornment> }),
  }} />
}
