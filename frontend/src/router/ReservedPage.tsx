import { Alert, Typography } from '@mui/material'

export function ReservedPage({ title }: { title: string }) {
  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 3 }}>{title}</Typography>
    <Alert severity="info">Sección reservada para un próximo incremento. Todavía no hay operaciones disponibles.</Alert>
  </section>
}
