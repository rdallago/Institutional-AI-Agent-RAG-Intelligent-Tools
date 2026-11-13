import { useEffect, useRef, useState } from 'react'
import { Alert, Button, Paper, Stack, TextField, Typography, Link } from '@mui/material'
import { useAuth } from '../../auth/model/authContext'
import { ApiError } from '../../../api/errors'
import { createConversationsApi } from '../api/conversationsApi'
import type { ChatMessage, Conversation } from '../api/conversationsApi'
import { validatePrompt } from '../model/promptPolicy'

export default function ConversationPanel() {
  const { get, mutate } = useAuth()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selected, setSelected] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const active = useRef<AbortController | null>(null)
  const generation = useRef(0)
  const alive = useRef(true)
  const locked = useRef(false)
  const retry = useRef<{ signature: string; key: string } | null>(null)
  const pendingCreation = useRef<string | null>(null)
  const [blocked, setBlocked] = useState(false)
  const cooldown = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    alive.current = true
    const controller = new AbortController()
    void createConversationsApi(get, mutate).list(controller.signal).then(rows => {
      if (controller.signal.aborted) return
      setConversations(rows); setSelected(rows[0]?.id ?? ''); setReady(true)
    }).catch(() => { if (!controller.signal.aborted) { setError('No pudimos recuperar tus conversaciones.'); setReady(true) } })
    return () => { alive.current = false; controller.abort(); active.current?.abort(); if (cooldown.current) clearTimeout(cooldown.current) }
  }, [get, mutate])
  useEffect(() => {
    if (!selected || busy) return
    const controller = new AbortController()
    void createConversationsApi(get, mutate).history(selected, controller.signal).then(rows => {
      if (!controller.signal.aborted) setMessages(rows)
    }).catch(() => { if (!controller.signal.aborted) { setMessages([]); setError('No pudimos recuperar el historial autorizado.') } })
    return () => controller.abort()
  }, [selected, get, mutate, busy])

  async function run(newOnly = false) {
    if (!ready || locked.current || blocked || (!newOnly && validatePrompt(prompt) !== true)) return
    locked.current = true; setBusy(true); setError('')
    const sequence = ++generation.current
    const controller = new AbortController(); active.current = controller
    const timer = setTimeout(() => controller.abort(), 70000)
    try {
      const api = createConversationsApi(get, mutate)
      let id = newOnly ? '' : selected
      if (!id) {
        pendingCreation.current ??= crypto.randomUUID()
        id = await api.create(controller.signal, pendingCreation.current)
        pendingCreation.current = null
        if (!alive.current || sequence !== generation.current) return
        setMessages([]); setSelected(id)
        setConversations(await api.list(controller.signal))
      }
      if (!newOnly) {
        const signature = JSON.stringify([id, prompt, 'AUTO'])
        if (retry.current?.signature !== signature) retry.current = { signature, key: crypto.randomUUID() }
        await api.turn(id, retry.current.key, prompt, 'AUTO', '', controller.signal)
        const history = await api.history(id, controller.signal)
        if (!alive.current || sequence !== generation.current) return
        setMessages(history); setPrompt(''); retry.current = null
      } else retry.current = null
    } catch (failure) {
      if (!alive.current || sequence !== generation.current) return
      const code = failure instanceof ApiError ? failure.status : undefined
      // Un error HTTP definitivo terminó el intento; el siguiente envío MANUAL es nuevo.
      // En errores de red/cancelación conservamos la clave para no duplicar trabajo incierto.
      if (code !== undefined && [403, 422, 429, 502, 503, 504].includes(code)) retry.current = null
      if (failure instanceof ApiError && code === 429 && failure.retryAfter !== undefined) {
        setBlocked(true)
        cooldown.current = setTimeout(() => setBlocked(false), failure.retryAfter * 1000)
      }
      setError(controller.signal.aborted ? 'Se canceló la espera. No se reenvía automáticamente; revisá el historial antes de intentar otra consulta.'
        : code === 403 ? 'No tenés permiso para esta conversación o sus documentos.'
          : code === 503 ? (failure instanceof ApiError && failure.code === 'IA_MEMORIA_INSUFICIENTE'
            ? 'No hay RAM suficiente para interpretar esta consulta con Qwen. Liberá recursos y volvé a enviarla manualmente.'
            : failure instanceof ApiError && failure.code === 'CLIMA_NO_DISPONIBLE'
              ? 'Open-Meteo no está disponible. No se inventaron datos meteorológicos.'
              : failure instanceof ApiError && failure.code === 'IA_PLANIFICADOR_NO_DISPONIBLE'
                ? 'El planificador Qwen/Ollama no está disponible. No se ejecutó una herramienta adivinada.'
                : 'El proveedor o servicio no está disponible. No se inventaron datos.')
            : code === 502 ? 'El modelo o proveedor devolvió un contrato inválido. No es ausencia de evidencia.'
              : code === 429 ? (failure instanceof ApiError && failure.code === 'IA_LIMITE_INTENTOS'
                ? `Alcanzaste la cuota temporal de consultas. Esperá ${failure.retryAfter ?? 60} segundos antes de enviar nuevamente.`
                : 'Hay una consulta en curso o un enfriamiento temporal. Esperá antes de enviar nuevamente.')
                : code === 504 ? 'Se agotó el tiempo del último envío. No se reintentó automáticamente ni se generó una respuesta alternativa. Las respuestas del historial anterior permanecen visibles.'
                : code === 422 ? 'Revisá la consulta: no incluyas contraseñas, tokens o secretos.'
                  : 'No pudimos completar la consulta. No se reintentó automáticamente.')
    } finally {
      clearTimeout(timer)
      if (alive.current && sequence === generation.current) { locked.current = false; setBusy(false); active.current = null }
    }
  }

  return <section>
    <Typography component="h1" variant="h3">Consultar IA</Typography>
    <Stack spacing={2} sx={{ maxWidth: 850, mt: 2 }}>
      <Alert severity="info">Historial privado guardado entre sesiones. No escribas contraseñas, tokens ni información confidencial.</Alert>
      <TextField label="Conversación" select SelectProps={{ native: true }} value={selected} disabled={busy}
        onChange={event => { setSelected(event.target.value); setMessages([]); setError(''); retry.current = null }}>
        {!selected && <option value="">Nueva conversación al enviar</option>}
        {conversations.map((c, i) => <option key={c.id} value={c.id}>Conversación {i + 1} · {new Date(c.creado_at).toLocaleString()}</option>)}
      </TextField>
      <Button disabled={!ready || busy || blocked} onClick={() => { void run(true) }}>Nueva conversación</Button>
      <Stack role="log" aria-label="Historial de conversación" spacing={2}>
        {messages.map(m => <Paper key={m.id} variant="outlined" sx={{ p: 2 }}>
          <Typography fontWeight="bold">{m.rol === 'user' ? 'Vos' : 'Asistente'}</Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{m.contenido}</Typography>
          {m.rol === 'assistant' && <>
            {m.fuentes.map(f => <Typography key={f.id}>[{f.id}] Página PDF {f.pagina}</Typography>)}
            {m.estrategia === 'TOOL' && <Link href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Datos meteorológicos por Open-Meteo</Link>}
          </>}
        </Paper>)}
      </Stack>
      <TextField label="Consulta" multiline minRows={3} value={prompt} disabled={busy}
        onChange={event => setPrompt(event.target.value)} helperText="Hasta 1000 caracteres Unicode y 3000 bytes UTF-8." />
      <Button variant="contained" disabled={!ready || busy || blocked || validatePrompt(prompt) !== true} onClick={() => { void run() }}>Enviar consulta</Button>
      {busy && <Button onClick={() => active.current?.abort()}>Cancelar espera</Button>}
      {busy && <Typography role="status">Procesando consulta…</Typography>}
      {error && <Alert severity="warning">{error}</Alert>}
    </Stack>
  </section>
}
