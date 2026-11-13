// No intercepta HTTP ni guarda capturas, trazas, contraseñas o tokens en disco.
import { spawn } from 'node:child_process'
import { mkdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const positive = process.argv[2] === 'positive'
const target = process.argv[3]
const folder = path.resolve('node_modules/.cache/chrome-85a6-' + Date.now())
await mkdir(folder, { recursive: true })
const chrome = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-extensions', '--disable-sync',
  '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1',
  `--user-data-dir=${folder}`, 'about:blank',
], { windowsHide: true, stdio: 'ignore' })
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket, send
let stage = 'startup'
const statuses = []
try {
  let port
  for (let i = 0; i < 100; i++) {
    try { port = Number((await readFile(path.join(folder, 'DevToolsActivePort'), 'utf8')).split('\n')[0]); break }
    catch { await sleep(100) }
  }
  if (!port) throw Error()
  const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json())
  socket = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let seq = 0, exceptions = 0
  const waiting = new Map()
  send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq; waiting.set(id, { resolve, reject }); socket.send(JSON.stringify({ id, method, params }))
  })
  socket.onmessage = event => {
    const msg = JSON.parse(event.data)
    if (msg.id) {
      const pending = waiting.get(msg.id); waiting.delete(msg.id)
      if (msg.error) pending.reject(Error()); else pending.resolve(msg.result)
    } else if (msg.method === 'Runtime.exceptionThrown') exceptions++
    else if (msg.method === 'Network.responseReceived') {
      const url = new URL(msg.params.response.url)
      if (url.pathname.startsWith('/api/')) statuses.push([url.pathname, msg.params.response.status])
    }
  }
  await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable')
  const ev = async expression => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.value
  const until = async expression => {
    for (let i = 0; i < 150; i++) { if (await ev(expression)) return; await sleep(100) }
    throw Error()
  }
  const click = async text => {
    const selector = `Array.from(document.querySelectorAll('button,a')).find(el=>el.textContent===${JSON.stringify(text)} && !el.disabled)`
    await until(`Boolean(${selector})`)
    await ev(`(${selector}).click()`)
  }
  const fill = values => ev(`(()=>{for(const [id,value] of ${JSON.stringify(values)}){const el=document.getElementById(id);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}))}})()`)
  const route = async pathname => {
    await ev(`history.pushState({},'',${JSON.stringify(pathname)});dispatchEvent(new PopStateEvent('popstate'))`)
  }
  const login = async (email, password) => {
    await until("Boolean(document.getElementById('login-email'))")
    await fill([['login-email', email], ['login-password', password]])
    await until("Boolean(Array.from(document.querySelectorAll('button')).find(el=>el.textContent==='Ingresar' && !el.disabled))")
    await sleep(100)
    await click('Ingresar')
  }
  const change = async current => {
    await until("Boolean(document.getElementById('password-current'))")
    await fill([['password-current', current], ['password-change-new', 'browser-definitive-password-2026'], ['password-change-confirm', 'browser-definitive-password-2026']])
    await sleep(100)
    await click('Guardar nueva contraseña')
    await until("Boolean(document.getElementById('login-email'))")
    if (await ev('localStorage.length+sessionStorage.length') !== 0) throw Error()
  }
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch('http://127.0.0.1:15173')).ok) break } catch { /* startup */ }
    await sleep(100)
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false })
  await send('Page.navigate', { url: 'http://127.0.0.1:15173/login' })
  stage = 'normal-admin-login'
  await login('operator@example.com', 'test-password-with-at-least-15-chars')
  await until("location.pathname==='/dashboard'")
  stage = 'admin-creation'
  await route('/usuarios/nuevo')
  await until("Boolean(document.getElementById('perfil-nombre'))")
  await fill([['perfil-nombre', 'Created'], ['perfil-apellido', 'Browser'], ['perfil-email', 'created-browser@example.com'],
    ['perfil-initial-new', 'browser-initial-password-2026'], ['perfil-initial-confirm', 'browser-initial-password-2026']])
  await click('Crear perfil')
  if (!positive) {
    await until("document.querySelector('[role=alert]')?.textContent.includes('habilitado') || Array.from(document.querySelectorAll('[role=alert]')).some(el=>el.textContent.includes('habilitado'))")
    if (await ev("location.pathname!=='/usuarios/nuevo' || document.body.innerText.includes('Perfil creado correctamente.')")) throw Error()
  } else {
    await until("document.body.innerText.includes('Perfil creado correctamente.')")
    await click('Cerrar sesión')
    stage = 'restricted-created-user'
    await login('created-browser@example.com', 'browser-initial-password-2026')
    await until("location.pathname==='/cambiar-password' && Boolean(document.getElementById('password-current'))")
    await route('/usuarios')
    await until("location.pathname==='/cambiar-password'")
    if (await ev("Boolean(document.querySelector('nav'))")) throw Error()
    stage = 'mandatory-created-user'
    await change('browser-initial-password-2026')
    await login('created-browser@example.com', 'browser-definitive-password-2026')
    await until("location.pathname==='/dashboard'")
    await click('Cerrar sesión')
    stage = 'historical-admin-login'
    await login('operator@example.com', 'test-password-with-at-least-15-chars')
    await until("location.pathname==='/dashboard'")
    stage = 'historical-detail'
    await route('/usuarios/' + target)
    await until("Boolean(Array.from(document.querySelectorAll('button')).find(el=>el.textContent==='Asignar contraseña inicial'))")
    await click('Asignar contraseña inicial')
    stage = 'historical-dialog'
    await until("Boolean(document.getElementById('assign-initial-new'))")
    await fill([['assign-initial-new', 'browser-initial-password-2026'], ['assign-initial-confirm', 'browser-initial-password-2026']])
    stage = 'historical-submit'
    await click('Confirmar asignación')
    await until("document.body.innerText.includes('Contraseña inicial asignada.')")
    await click('Cerrar sesión')
    stage = 'mandatory-historical-user'
    await login('historic-browser@example.com', 'browser-initial-password-2026')
    await change('browser-initial-password-2026')
    await login('historic-browser@example.com', 'browser-definitive-password-2026')
    await until("location.pathname==='/dashboard'")
    await click('Cerrar sesión')
    await until("Boolean(document.getElementById('login-email'))")
  }
  if (exceptions || await ev('localStorage.length+sessionStorage.length')) throw Error()
  console.log('REAL_BROWSER_OK ' + (positive ? 'creation-assignment-mandatory-login-logout' : 'closed-gate-no-fake-success'))
} catch {
  console.error('REAL_BROWSER_FAILED stage=' + stage + ' statuses=' + JSON.stringify(statuses))
  process.exitCode = 1
} finally {
  if (send) { try { await send('Browser.close') } catch { /* owned process cleanup */ } }
  socket?.close(); chrome.kill()
}
