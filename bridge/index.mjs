// Bizro WhatsApp bridge: a QR-linked WhatsApp number stands in for the Cloud API
// while the WABA is locked. Two directions:
//   inbound  WhatsApp -> Cloud-API-shaped webhook POST (signed) -> BACKEND/webhook/whatsapp
//   outbound backend POST {GRAPH_BASE}/{phone_id}/messages and media GETs -> this server
// The backend only needs WHATSAPP_GRAPH_BASE=http://<bridge>:<port>.
import http from 'node:http'
import crypto from 'node:crypto'
import fs from 'node:fs'
import makeWASocket, {
  useMultiFileAuthState, DisconnectReason, downloadMediaMessage, fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys'
import pino from 'pino'
import qrTerminal from 'qrcode-terminal'
import QRCode from 'qrcode'

const PORT = Number(process.env.BRIDGE_PORT || 8090)
const BACKEND = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '')
const APP_SECRET = process.env.WHATSAPP_APP_SECRET || ''
const PHONE_ID = process.env.WHATSAPP_PHONE_NUMBER_ID || 'bridge'
const AUTH_DIR = process.env.AUTH_DIR || './auth'
const SELF_URL = (process.env.BRIDGE_SELF_URL || `http://localhost:${PORT}`).replace(/\/$/, '')
const log = pino({ level: process.env.LOG_LEVEL || 'info' })

let sock = null
let lastQr = null
let connected = false
const media = new Map()        // media_id -> { buf, mime }
const jidFor = new Map()       // wa_id (digits) -> chat jid to reply to
const lastButtons = new Map()  // wa_id -> [{id, title}]

const digits = (jid) => (jid || '').split('@')[0].split(':')[0].replace(/\D/g, '')

function senderOf(key) {
  // WhatsApp now hides numbers behind @lid ids; Baileys 7 carries the phone
  // jid alongside as remoteJidAlt/senderPn when it knows it.
  const candidates = [key.remoteJid, key.remoteJidAlt, key.senderPn, key.participantAlt]
  const pn = candidates.find((j) => j && j.endsWith('@s.whatsapp.net'))
  return { waId: digits(pn || key.remoteJid), replyJid: key.remoteJid }
}

function sign(raw) {
  return 'sha256=' + crypto.createHmac('sha256', APP_SECRET).update(raw).digest('hex')
}

async function postWebhook(waId, name, message) {
  const payload = {
    object: 'whatsapp_business_account',
    entry: [{
      id: 'bridge',
      changes: [{
        field: 'messages',
        value: {
          messaging_product: 'whatsapp',
          metadata: { display_phone_number: digits(sock?.user?.id), phone_number_id: PHONE_ID },
          contacts: [{ profile: { name: name || waId }, wa_id: waId }],
          messages: [{ from: waId, timestamp: String(Math.floor(Date.now() / 1000)), ...message }],
        },
      }],
    }],
  }
  const raw = JSON.stringify(payload)
  const headers = { 'content-type': 'application/json' }
  if (APP_SECRET) headers['x-hub-signature-256'] = sign(raw)
  try {
    const r = await fetch(`${BACKEND}/webhook/whatsapp`, { method: 'POST', headers, body: raw })
    log.info({ waId, type: message.type, status: r.status }, 'inbound -> backend')
  } catch (e) {
    log.error({ err: String(e) }, 'backend webhook POST failed')
  }
}

function unwrap(m) {
  // ephemeral / view-once / edited wrappers
  return m?.ephemeralMessage?.message || m?.viewOnceMessage?.message
    || m?.viewOnceMessageV2?.message || m?.documentWithCaptionMessage?.message || m
}

async function onMessage(msg) {
  if (!msg.message || msg.key.fromMe) return
  const jid = msg.key.remoteJid || ''
  if (jid.endsWith('@g.us') || jid === 'status@broadcast' || jid.endsWith('@newsletter')) return
  const { waId, replyJid } = senderOf(msg.key)
  jidFor.set(waId, replyJid)
  const m = unwrap(msg.message)
  const id = 'wamid.' + (msg.key.id || crypto.randomUUID())
  const name = msg.pushName

  const text = m.conversation || m.extendedTextMessage?.text
  if (text != null) {
    // A typed number/title that matches the buttons we last rendered becomes a
    // button tap, so the backend's one-tap confirm flow still works.
    const btns = lastButtons.get(waId) || []
    const t = text.trim()
    const hit = btns[Number(t) - 1] || btns.find((b) => b.title.toLowerCase() === t.toLowerCase())
    if (hit) {
      lastButtons.delete(waId)
      return postWebhook(waId, name, {
        id, type: 'interactive',
        interactive: { type: 'button_reply', button_reply: { id: hit.id, title: hit.title } },
      })
    }
    return postWebhook(waId, name, { id, type: 'text', text: { body: text } })
  }

  const kind = m.audioMessage ? 'audio' : m.imageMessage ? 'image' : null
  if (!kind) { log.info({ waId, keys: Object.keys(m) }, 'unsupported message ignored'); return }
  const node = m.audioMessage || m.imageMessage
  let buf
  try {
    buf = await downloadMediaMessage(msg, 'buffer', {}, { logger: log, reuploadRequest: sock.updateMediaMessage })
  } catch (e) { log.error({ err: String(e) }, 'media download failed'); return }
  const mediaId = crypto.randomUUID()
  const mime = (node.mimetype || (kind === 'audio' ? 'audio/ogg' : 'image/jpeg')).split(';')[0]
  media.set(mediaId, { buf, mime: node.mimetype || mime })
  setTimeout(() => media.delete(mediaId), 30 * 60 * 1000)
  const body = { id: mediaId, mime_type: mime }
  if (kind === 'audio') body.voice = !!node.ptt
  if (kind === 'image' && node.caption) body.caption = node.caption
  return postWebhook(waId, name, { id, type: kind, [kind]: body })
}

function renderOutbound(waId, msg) {
  if (msg.type === 'interactive') {
    const inter = msg.interactive || {}
    const btns = (inter.action?.buttons || []).map((b) => ({ id: b.reply?.id, title: b.reply?.title }))
    lastButtons.set(waId, btns)
    const lines = btns.map((b, i) => `${i + 1}. ${b.title}`)
    return [inter.body?.text || '', '', ...lines, '', 'Reply with the number.'].join('\n').trim()
  }
  return msg.text?.body || ''
}

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR)
  const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }))
  sock = makeWASocket({ auth: state, version, logger: log.child({ level: 'warn' }), browser: ['Bizro', 'Chrome', '1.0'] })
  sock.ev.on('creds.update', saveCreds)
  sock.ev.on('connection.update', ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      lastQr = qr
      log.info(`Scan this QR in WhatsApp > Linked devices (or open ${SELF_URL}/qr):`)
      qrTerminal.generate(qr, { small: true })
    }
    if (connection === 'open') { connected = true; lastQr = null; log.info({ me: sock.user?.id }, 'WhatsApp connected') }
    if (connection === 'close') {
      connected = false
      const code = lastDisconnect?.error?.output?.statusCode
      if (code === DisconnectReason.loggedOut) {
        log.warn('logged out — clearing session, a new QR will follow')
        fs.rmSync(AUTH_DIR, { recursive: true, force: true })
      }
      setTimeout(connect, 2000)
    }
  })
  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return
    for (const m of messages) await onMessage(m).catch((e) => log.error({ err: String(e) }, 'onMessage'))
  })
}

const json = (res, code, obj) => { res.writeHead(code, { 'content-type': 'application/json' }); res.end(JSON.stringify(obj)) }

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x')
  const parts = url.pathname.split('/').filter(Boolean)
  try {
    if (req.method === 'GET' && url.pathname === '/health') return json(res, 200, { connected, me: sock?.user?.id || null, qr_pending: !!lastQr })
    if (req.method === 'GET' && url.pathname === '/qr') {
      if (connected) { res.writeHead(200, { 'content-type': 'text/html' }); return res.end('<h2>WhatsApp connected ✅</h2>') }
      if (!lastQr) { res.writeHead(200, { 'content-type': 'text/html' }); return res.end('<meta http-equiv="refresh" content="2">Waiting for QR…') }
      const svg = await QRCode.toString(lastQr, { type: 'svg', margin: 2, width: 360 })
      res.writeHead(200, { 'content-type': 'text/html' })
      return res.end(`<meta http-equiv="refresh" content="15"><h3>WhatsApp → Linked devices → Link a device</h3>${svg}`)
    }
    // Graph: POST /{phone_id}/messages
    if (req.method === 'POST' && parts[1] === 'messages') {
      let raw = ''; for await (const c of req) raw += c
      const msg = JSON.parse(raw || '{}')
      const waId = digits(msg.to)
      if (!connected) return json(res, 503, { error: { message: 'bridge not connected to WhatsApp' } })
      const jid = jidFor.get(waId) || `${waId}@s.whatsapp.net`
      const sent = await sock.sendMessage(jid, { text: renderOutbound(waId, msg) })
      log.info({ to: waId }, 'outbound sent')
      return json(res, 200, { messaging_product: 'whatsapp', contacts: [{ input: msg.to, wa_id: waId }], messages: [{ id: 'wamid.' + sent?.key?.id }] })
    }
    // Graph: GET /media-bytes/{id} (the url we hand out below)
    if (req.method === 'GET' && parts[0] === 'media-bytes' && media.has(parts[1])) {
      const m = media.get(parts[1]); res.writeHead(200, { 'content-type': m.mime }); return res.end(m.buf)
    }
    // Graph: GET /{media_id} -> metadata with a download url
    if (req.method === 'GET' && parts.length === 1 && media.has(parts[0])) {
      const m = media.get(parts[0])
      return json(res, 200, { id: parts[0], mime_type: m.mime, file_size: m.buf.length, url: `${SELF_URL}/media-bytes/${parts[0]}` })
    }
    json(res, 404, { error: { message: 'not found' } })
  } catch (e) {
    log.error({ err: String(e) }, 'http handler'); json(res, 500, { error: { message: String(e) } })
  }
}).listen(PORT, () => log.info(`bridge listening on :${PORT}, backend ${BACKEND}`))

connect()
