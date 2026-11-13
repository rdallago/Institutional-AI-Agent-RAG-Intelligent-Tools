// Auditoría sin MSW, sin trazas HTTP ni secretos en artefactos.
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
const [browser, executable, target] = process.argv.slice(2)
const firefox = browser === 'firefox'
const folder = path.resolve(`node_modules/.cache/audit-86a-${browser}-${Date.now()}`)
await mkdir(folder, { recursive: true })
const child = spawn(executable, firefox
  ? ['--headless', '--no-remote', '--profile', folder, '--remote-debugging-port', '19191', 'about:blank']
  : ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
    '--disable-extensions', '--disable-sync', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1', `--user-data-dir=${folder}`, 'about:blank'],
{ windowsHide: true, stdio: 'ignore' })
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
let socket, send, context, stage = 'startup', lastMethod = '', protocolError = ''
const report = { browser, screens: [], keyboard: [], issues: [] }
try {
  let endpoint
  for (let i = 0; i < 300; i++) {
    try {
      if (firefox) {
        await fetch('http://127.0.0.1:19191/status')
        endpoint = 'ws://127.0.0.1:19191/session'
      } else {
        const port = Number((await readFile(path.join(folder, 'DevToolsActivePort'), 'utf8')).split('\n')[0])
        const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then(r => r.json())
        endpoint = pages.find(page => page.type === 'page').webSocketDebuggerUrl
      }
      break
    } catch { await sleep(100) }
  }
  if (!endpoint) throw Error('protocol unavailable')
  stage = 'websocket'
  socket = new WebSocket(endpoint)
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
  let seq = 0
  const waiting = new Map()
  send = (method, params = {}) => new Promise((resolve, reject) => {
    lastMethod = method
    const id = ++seq
    const timeout = setTimeout(() => { waiting.delete(id); reject(Error('protocol timeout')) }, 25000)
    waiting.set(id, { resolve, reject, timeout })
    socket.send(JSON.stringify({ id, method, params }))
  })
  socket.onmessage = event => {
    const msg = JSON.parse(event.data)
    if (msg.id) {
      const item = waiting.get(msg.id)
      if (!item) return
      clearTimeout(item.timeout); waiting.delete(msg.id)
      if (msg.error) { protocolError = typeof msg.error === 'string' ? msg.error : 'cdp-error'; item.reject(Error('protocol command')) } else item.resolve(msg.result)
    }
  }
  if (firefox) {
    stage = 'bidi-session'
    const session = await send('session.new', { capabilities: {} })
    report.version = session.capabilities.browserVersion
    context = (await send('browsingContext.create', { type: 'tab' })).context
  } else {
    stage = 'cdp-session'
    report.version = (await send('Browser.getVersion')).product
    await send('Page.enable'); await send('Runtime.enable')
  }
  const ev = async expression => {
    if (firefox) {
      const result = await send('script.evaluate', { expression, target: { context }, awaitPromise: true })
      if (result.type === 'exception') throw Error('page expression')
      return result.result.value
    }
    const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails) throw Error('page expression')
    return result.result.value
  }
  const until = async expression => {
    for (let i = 0; i < 150; i++) { if (await ev(expression)) return; await sleep(100) }
    throw Error('condition')
  }
  const click = async text => {
    const selector = `Array.from(document.querySelectorAll('button,a')).find(el=>el.textContent===${JSON.stringify(text)} && !el.disabled)`
    await until(`Boolean(${selector})`); await ev(`(()=>{const el=${selector};el.focus();el.click()})()`)
  }
  const fill = values => ev(`(()=>{for(const [id,value] of ${JSON.stringify(values)}){const el=document.getElementById(id);Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}))}})()`)
  const route = async pathname => {
    await ev(`history.pushState({},'',${JSON.stringify(pathname)});dispatchEvent(new PopStateEvent('popstate'))`)
  }
  const viewport = async (width, height) => firefox
    ? send('browsingContext.setViewport', { context, viewport: { width, height }, devicePixelRatio: 1 })
    : send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 })
  const shot = async name => {
    const data = firefox
      ? (await send('browsingContext.captureScreenshot', { context, origin: 'viewport' })).data
      : (await send('Page.captureScreenshot')).data
    await writeFile(path.join(folder, name + '.png'), Buffer.from(data, 'base64'))
  }
  const inspect = async name => {
    stage = name
    for (const [size, width, height] of [['desktop', 1280, 900], ['mobile', 390, 844]]) {
      await viewport(width, height); await sleep(250)
      const summary = JSON.parse(await ev(`JSON.stringify({overflow:document.documentElement.scrollWidth>innerWidth,unlabelled:Array.from(document.querySelectorAll('input:not([type=hidden]):not([aria-hidden=true])')).filter(el=>!el.labels?.length&&!el.getAttribute('aria-label')&&!el.getAttribute('aria-labelledby')).length,unnamedButtons:Array.from(document.querySelectorAll('button')).filter(el=>!el.textContent.trim()&&!el.getAttribute('aria-label')&&!el.getAttribute('aria-labelledby')).length,comboboxes:Array.from(document.querySelectorAll('[role=combobox]')).map(el=>({label:el.getAttribute('aria-label')||(el.getAttribute('aria-labelledby')||'').split(' ').map(id=>document.getElementById(id)?.textContent||'').join(' ')}))})`))
      report.screens.push({ name, size, ...summary })
      await shot(name + '-' + size)
    }
    await viewport(1280, 900)
  }
  const tab = async () => {
    if (firefox) {
      await send('input.performActions', { context, actions: [{ type: 'key', id: 'keyboard', actions: [{ type: 'keyDown', value: '\uE004' }, { type: 'keyUp', value: '\uE004' }] }] })
    } else {
      await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
      await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 })
    }
  }
  const login = async email => {
    await until("Boolean(document.getElementById('login-email'))")
    await fill([['login-email', email], ['login-password', 'test-password-with-at-least-15-chars']])
    await click('Ingresar')
  }
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch('http://127.0.0.1:15174')).ok) break } catch { /* startup */ }
    await sleep(100)
  }
  await viewport(1280, 900)
  if (firefox) await send('browsingContext.navigate', { context, url: 'http://127.0.0.1:15174/login', wait: 'complete' })
  else await send('Page.navigate', { url: 'http://127.0.0.1:15174/login' })
  await until("Boolean(document.getElementById('login-email'))")
  await inspect('login')
  await ev("document.getElementById('login-email').focus()")
  for (let i = 0; i < 3; i++) {
    await tab()
    report.keyboard.push(JSON.parse(await ev("JSON.stringify((()=>{const el=document.activeElement;const styled=el.tagName==='INPUT'?el.closest('.MuiOutlinedInput-root'):el;const css=getComputedStyle(styled);return {id:el.id,tag:el.tagName,name:el.getAttribute('aria-label')||el.textContent,focusVisible:el.matches(':focus-visible'),outlineWidth:css.outlineWidth,outlineStyle:css.outlineStyle}})())")))
  }
  await shot('login-keyboard-focus')
  report.focusStyle = JSON.parse(await ev("JSON.stringify((()=>{const el=document.activeElement;const read=()=>{const c=getComputedStyle(el);return {outline:c.outline,shadow:c.boxShadow,background:c.backgroundColor,border:c.border}};const focused=read();el.blur();return {focused,blurred:read()}})())"))
  // MUI retira Mui-focusVisible en el siguiente render tras blur.
  await sleep(150)
  report.focusStyle.blurred = JSON.parse(await ev("JSON.stringify((()=>{const el=Array.from(document.querySelectorAll('button')).find(el=>el.textContent==='Ingresar');const c=getComputedStyle(el);return {outline:c.outline,shadow:c.boxShadow,background:c.backgroundColor,border:c.border}})())"))
  if (report.keyboard.some(item => item.outlineWidth !== '3px' || item.outlineStyle !== 'solid')) throw Error('focus indicator')
  if (report.focusStyle.focused.outline === report.focusStyle.blurred.outline) throw Error('focus unchanged')
  await click('Ingresar')
  await until("Boolean(document.querySelector('[aria-invalid=true]'))")
  await inspect('login-validation')
  await login('operator@example.com')
  await until("location.pathname==='/dashboard' && Boolean(document.querySelector('nav'))")
  await inspect('dashboard')
  await route('/usuarios')
  await until("document.body.innerText.includes('quality-target@example.com')")
  await inspect('list')
  await route('/usuarios/' + target)
  await until("document.body.innerText.includes('Detalle de perfil') && document.body.innerText.includes('quality-target@example.com')")
  await inspect('detail')
  await click('Asignar contraseña inicial')
  await until("Boolean(document.getElementById('assign-initial-new'))")
  await inspect('assignment')
  await ev("document.querySelector('[role=dialog] button')?.focus()")
  for (let i = 0; i < 8; i++) await tab()
  report.dialogFocusContained = await ev("document.querySelector('[role=dialog]').contains(document.activeElement)")
  await click('Cancelar')
  await sleep(400)
  report.dialogFocusRestored = await ev("document.activeElement.textContent==='Asignar contraseña inicial'")
  await click('Editar')
  await until("Boolean(document.getElementById('perfil-nombre'))")
  await inspect('edit')
  await route('/usuarios/nuevo')
  await until("Boolean(document.getElementById('perfil-initial-new'))")
  await inspect('create')
  await fill([['perfil-nombre', 'Quality'], ['perfil-apellido', 'Fixture'], ['perfil-email', 'quality-create@example.com'], ['perfil-initial-new', 'quality-initial-password-fictional'], ['perfil-initial-confirm', 'quality-initial-password-fictional']])
  await click('Crear perfil')
  await until("Array.from(document.querySelectorAll('[role=alert]')).some(el=>el.textContent.includes('habilitado'))")
  await inspect('closed-gate-error')
  await route('/cambiar-password')
  await until("Boolean(document.getElementById('password-current'))")
  await inspect('voluntary')
  await click('Cerrar sesión')
  await until("Boolean(document.getElementById('login-email'))")
  await ev('history.back()'); await sleep(300)
  await until("Boolean(document.getElementById('login-email'))")
  report.privateAfterLogout = await ev("document.body.innerText.includes('quality-target@example.com') || Boolean(document.querySelector('nav'))")
  await login('quality-pending@example.com')
  await until("location.pathname==='/cambiar-password' && Boolean(document.getElementById('password-current'))")
  await inspect('mandatory')
  await route('/usuarios')
  await until("location.pathname==='/cambiar-password'")
  report.pendingAdminHasNavigation = await ev("Boolean(document.querySelector('nav'))")
  await click('Cerrar sesión')
  await until("Boolean(document.getElementById('login-email'))")
  report.storageEntries = await ev('localStorage.length+sessionStorage.length')
  await writeFile(path.join(folder, 'report.json'), JSON.stringify(report, null, 2))
  if (report.privateAfterLogout || report.pendingAdminHasNavigation || report.storageEntries) throw Error('privacy')
  console.log('QUALITY_OK ' + JSON.stringify({ browser, version: report.version, screens: report.screens.length, report: path.join(folder, 'report.json') }))
} catch {
  await writeFile(path.join(folder, 'report.json'), JSON.stringify(report, null, 2))
  console.error('QUALITY_FAILED browser=' + browser + ' stage=' + stage + ' method=' + lastMethod + ' error=' + protocolError)
  process.exitCode = 1
} finally {
  if (send) { try { await send(firefox ? 'browser.close' : 'Browser.close') } catch { /* cleanup */ } }
  socket?.close(); child.kill()
}
