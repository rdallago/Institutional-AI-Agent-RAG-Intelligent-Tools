import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    primary: { main: '#1c5d58', contrastText: '#ffffff' },
    background: { default: '#f2f4f0', paper: '#ffffff' },
    text: { primary: '#172e37', secondary: '#56656b' },
    error: { main: '#a52c30' },
    divider: '#dbe2dd',
  },
  typography: {
    fontFamily: '"Segoe UI", system-ui, sans-serif',
    h2: { fontWeight: 650, fontSize: 'clamp(2.2rem, 4vw, 3.6rem)', lineHeight: 1.12, letterSpacing: '-.045em' },
    h3: { fontWeight: 650, fontSize: 'clamp(1.8rem, 4vw, 2.8rem)', letterSpacing: '-.03em' },
    h4: { fontWeight: 650, fontSize: '1.85rem', letterSpacing: '-.025em' },
    h5: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 650 },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { minHeight: 46 } } },
    // ButtonBase cubre botones, iconos y enlaces interactivos de MUI.
    MuiButtonBase: { styleOverrides: { root: {
      '&.Mui-focusVisible, &:focus-visible': {
        outline: '3px solid #172e37',
        outlineOffset: 3,
        '@media (forced-colors: active)': { outlineColor: 'Highlight' },
      },
    } } },
    MuiOutlinedInput: { styleOverrides: { root: {
      '&:has(input:focus-visible), &:has([role="combobox"]:focus-visible)': {
        outline: '3px solid #172e37', outlineOffset: 3,
        '@media (forced-colors: active)': { outlineColor: 'Highlight' },
      },
    } } },
  },
})
