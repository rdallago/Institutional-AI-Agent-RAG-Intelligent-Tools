import type { ReactNode } from 'react'
import { CssBaseline, ThemeProvider } from '@mui/material'
import { AuthProvider } from '../features/auth/model/AuthProvider'
import { theme } from './theme'

export function AppProviders({ children }: { children: ReactNode }) {
  return <ThemeProvider theme={theme}><CssBaseline /><AuthProvider>{children}</AuthProvider></ThemeProvider>
}
