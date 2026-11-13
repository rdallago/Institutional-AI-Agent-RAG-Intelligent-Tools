import { useEffect, useRef, useState } from 'react'
import { Alert, Box, Button, CircularProgress, Paper, Stack, TextField, Typography } from '@mui/material'
import { useForm, useWatch } from 'react-hook-form'
import { ApiError } from '../../../api/errors'
import { useAuth } from '../../auth/model/authContext'
import { createIAApi } from '../api/iaApi'
import type { ConsultaIARespuesta, AgentResponse } from '../api/iaApi'
import { textMetrics, validatePrompt } from '../model/promptPolicy'
import ConversationPanel from './ConversationPanel'

function failureMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return 'No pudimos completar la consulta.'
  if (error.kind === 'network') return 'No pudimos conectar con el servidor. Revisá la conexión y reintentá manualmente.'
  if (error.kind === 'contract') return 'El servidor devolvió una respuesta inesperada. No se mostrará su contenido.'
  switch (error.status) {
    case 401: return 'La sesión ya no es válida. Ingresá nuevamente.'
    case 403: return 'No tenés acceso a esta consulta con el estado actual de tu sesión.'
    case 413: return 'La solicitud es demasiado grande. Acortá la consulta.'
    case 422: return 'El servidor rechazó la consulta. Revisá su contenido y sus límites.'
    case 429: return error.code === 'IA_OCUPADA' ? 'El servicio de IA está ocupado. Esperá antes de reintentar.' : 'Se alcanzó el límite de consultas. Esperá antes de reintentar.'
    case 502: return 'El servicio de IA devolvió una respuesta inválida. Reintentá más tarde.'
    case 503: return 'El servicio de IA no está disponible. Tu sesión sigue activa.'
    case 504: return 'Se agotó el tiempo de generación. El cálculo podría continuar en el servidor; no se reenviará la consulta.'
    default: return 'No pudimos completar la consulta. Reintentá más tarde.'
  }
}

function DiagnosticPage() {
  const { mutate, get } = useAuth()
  const [mode, setMode] = useState<'LLM_DIRECTO' | 'RAG' | 'AUTO'>('AUTO')
  const [documents, setDocuments] = useState<{ id: string; titulo: string }[]>([])
  const [document, setDocument] = useState('')
  const { register, control, handleSubmit, reset, formState: { errors } } = useForm<{ prompt: string }>({
    defaultValues: { prompt: '' }, mode: 'onChange',
  })
  const prompt = useWatch({ control, name: 'prompt' })
  const metrics = textMetrics(prompt)
  const [busy, setBusy] = useState(false)
  const [response, setResponse] = useState<ConsultaIARespuesta | AgentResponse | null>(null)
  const [message, setMessage] = useState('')
  const [remaining, setRemaining] = useState<number | null>(null)
  const active = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const locked = useRef(false)
  const alive = useRef(true)
  const deadline = useRef(0)
  useEffect(() => {
    if (mode === 'LLM_DIRECTO') return
    const controller = new AbortController()
    void get('/ia/documentos', controller.signal).then(value => {
      if (controller.signal.aborted) return
      if (!Array.isArray(value) || value.length > 50 || !value.every(d => typeof d === 'object' && d !== null
        && Object.keys(d).sort().join(',') === 'id,titulo' && typeof d.id === 'string'
        && /^[0-9a-f-]{36}$/i.test(d.id) && typeof d.titulo === 'string' && d.titulo.length <= 300)) {
        setMessage('El servidor devolvió documentos inesperados.'); return
      }
      setDocuments(value); setDocument(value[0]?.id ?? '')
      if (value.length === 0 && mode === 'RAG') setMessage('No hay documentos indexados disponibles para tu sesión.')
    }).catch(() => { if (!controller.signal.aborted) setMessage('No pudimos cargar los documentos disponibles.') })
    return () => controller.abort()
  }, [mode, get])
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false; sequence.current += 1; active.current?.abort() }
  }, [])
  useEffect(() => {
    if (remaining === null || remaining <= 0) return
    const timer = setInterval(() => setRemaining(Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000))), 500)
    return () => clearInterval(timer)
  }, [remaining])

  async function submit(input: { prompt: string }) {
    if (locked.current || Date.now() < deadline.current || (mode === 'RAG' && !document)) return
    locked.current = true
    const current = ++sequence.current
    const controller = new AbortController()
    active.current = controller
    setBusy(true); setResponse(null); setMessage('')
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, 70000)
    reset()
    try {
      const api = createIAApi(mutate)
      const result = mode === 'RAG' ? await api.rag(input.prompt, document, controller.signal)
        : mode === 'AUTO' ? await api.auto(input.prompt, document, controller.signal)
          : await api.consultar(input.prompt, controller.signal)
      if (alive.current && current === sequence.current) setResponse(result)
    } catch (error) {
      if (!alive.current || current !== sequence.current) return
      if (timedOut) {
        setMessage('Se agotó la espera local. El cálculo podría continuar en el servidor; no se reenviará la consulta.')
      } else if (!(error instanceof ApiError) || error.kind !== 'cancelled') {
        setMessage(failureMessage(error))
        if (error instanceof ApiError && error.status === 429) {
          if (error.retryAfter !== undefined) {
            deadline.current = Date.now() + error.retryAfter * 1000
            setRemaining(error.retryAfter)
          } else {
            setRemaining(null)
            setMessage(failureMessage(error) + ' El servidor no indicó un tiempo de espera.')
          }
        }
      }
    } finally {
      clearTimeout(timer)
      if (alive.current && current === sequence.current) {
        active.current = null; locked.current = false; setBusy(false)
      }
    }
  }

  function cancel() {
    sequence.current += 1
    active.current?.abort(); active.current = null; locked.current = false
    setBusy(false); setResponse(null)
    setMessage('Consulta cancelada. El cálculo podría continuar en el servidor; no se reenviará automáticamente.')
  }

  return <section>
    <Typography component="h1" variant="h3" sx={{ mb: 3 }}>Consultar IA</Typography>
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 4 }, borderRadius: 3, maxWidth: 800 }}>
      <Stack spacing={2.5}>
        <Alert severity="info">Las respuestas pueden contener errores. No envíes contraseñas, datos personales ni información confidencial.</Alert>
        <Box component="form" noValidate aria-busy={busy} onSubmit={event => { void handleSubmit(submit)(event) }}>
          <Stack spacing={2}>
            <TextField label="Estrategia" select SelectProps={{ native: true }} disabled={busy} value={mode}
              helperText={mode === 'AUTO' ? 'AUTO usa evidencia autorizada para consultas institucionales y LLM_DIRECTO para preguntas generales. Si falta contexto, pide precisión sin inventar.' : undefined}
              onChange={event => { setMode(event.target.value as 'LLM_DIRECTO' | 'RAG' | 'AUTO'); setDocuments([]); setDocument(''); setResponse(null); setMessage('') }}>
              <option value="AUTO">AUTO</option><option value="LLM_DIRECTO">LLM_DIRECTO</option><option value="RAG">RAG académico</option>
            </TextField>
            {mode !== 'LLM_DIRECTO' && <TextField label="Documento" select SelectProps={{ native: true }} disabled={busy}
              value={document} onChange={event => setDocument(event.target.value)}>
              {documents.length === 0 && <option value="">Sin documentos disponibles</option>}
              {documents.map(d => <option key={d.id} value={d.id}>{d.titulo}</option>)}
            </TextField>}
            <TextField label="Consulta" multiline minRows={4} fullWidth disabled={busy}
              {...register('prompt', { validate: validatePrompt })} error={Boolean(errors.prompt)}
              helperText={errors.prompt?.message ?? `${metrics.points}/1000 caracteres Unicode · ${metrics.bytes ?? '—'}/3000 bytes UTF-8`} />
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <Button type="submit" variant="contained" disabled={busy || (remaining ?? 0) > 0 || validatePrompt(prompt) !== true || (mode === 'RAG' && !document)}>Enviar consulta</Button>
              {busy && <Button onClick={cancel}>Cancelar consulta</Button>}
              {!busy && <Button onClick={() => { reset(); setResponse(null); setMessage('') }}>Limpiar</Button>}
            </Stack>
          </Stack>
        </Box>
        {busy && <Stack direction="row" spacing={1} role="status"><CircularProgress size={20} /><Typography>Generando respuesta…</Typography></Stack>}
        {message && <Alert severity="warning">{message}</Alert>}
        {remaining !== null && <Typography role="status">Podés reintentar en {remaining} segundos.</Typography>}
        {response && <Box component="section" aria-label="Respuesta de IA" sx={{ minWidth: 0 }}>
          <Typography component="h2" variant="h5" sx={{ mb: 1 }}>Respuesta</Typography>
          <Typography>Estrategia: {'estrategia' in response ? response.estrategia : 'LLM_DIRECTO'}</Typography>
          {'estado' in response && <Typography>Estado: {response.estado}</Typography>}
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{response.respuesta}</Typography>
          {'fuentes' in response && response.fuentes.map(f => <Typography key={f.id}>[{f.id}] Página PDF {f.pagina}</Typography>)}
          {response.finalizacion !== null && <Typography variant="body2" sx={{ mt: 2 }}>Finalización: {response.finalizacion === 'completa' ? 'completa' : 'límite de generación alcanzado'}</Typography>}
        </Box>}
      </Stack>
    </Paper>
  </section>
}

export default function ConsultaIAPage() {
  const [diagnostic, setDiagnostic] = useState(false)
  return <>
    <Button onClick={() => setDiagnostic(value => !value)}>{diagnostic ? 'Volver a conversaciones' : 'Diagnóstico sin historial'}</Button>
    {diagnostic ? <DiagnosticPage /> : <ConversationPanel />}
  </>
}
