import { Button, Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle } from '@mui/material'

export function ConfirmDialog({ open, title, description, busy, confirm, cancel }: {
  open: boolean; title: string; description: string; busy: boolean; confirm: () => void; cancel: () => void
}) {
  return <Dialog open={open} onClose={busy ? undefined : cancel} aria-labelledby="confirm-title" aria-describedby="confirm-description">
    <DialogTitle id="confirm-title">{title}</DialogTitle>
    <DialogContent><DialogContentText id="confirm-description">{description}</DialogContentText></DialogContent>
    <DialogActions>
      <Button onClick={cancel} disabled={busy} autoFocus>Cancelar</Button>
      <Button onClick={confirm} disabled={busy} variant="contained">{busy ? 'Aplicando…' : 'Confirmar operación'}</Button>
    </DialogActions>
  </Dialog>
}
