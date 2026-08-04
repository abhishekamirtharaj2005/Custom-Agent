#!/usr/bin/env node
'use strict';

/**
 * Hermclaw WhatsApp sidecar.
 *
 * Bridges Baileys (a WhatsApp Web protocol client -- JS-only, there is no
 * viable pure-Python equivalent, which is why this one channel is a
 * subprocess rather than native Python) to the Python WhatsAppChannel
 * adapter over newline-delimited JSON-RPC on stdin/stdout.
 *
 * Run via: node index.js   (after `npm install` in this directory)
 * Auth state persists under HERMCLAW_WHATSAPP_AUTH_DIR (default: ./.wa-auth
 * relative to cwd -- the Python adapter sets cwd to the profile's
 * workspace directory so this stays profile-scoped).
 *
 * First run: watch for a `qr` notification on stdout (or check stderr
 * logs) and scan it from WhatsApp > Linked Devices.
 */

const readline = require('readline');
const path = require('path');

let baileys;
try {
  baileys = require('@whiskeysockets/baileys');
} catch (err) {
  process.stderr.write(
    'Failed to load @whiskeysockets/baileys -- run `npm install` in this directory first.\n'
  );
  process.exit(1);
}

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = baileys;

const AUTH_DIR = process.env.HERMCLAW_WHATSAPP_AUTH_DIR || path.join(process.cwd(), '.wa-auth');

const rl = readline.createInterface({ input: process.stdin, terminal: false });

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + '\n');
}

function notify(method, params) {
  emit({ jsonrpc: '2.0', method, params });
}

function respond(id, result) {
  emit({ jsonrpc: '2.0', id, result });
}

function respondError(id, message) {
  emit({ jsonrpc: '2.0', id, error: { message: String(message) } });
}

let sock = null;

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);

  sock = makeWASocket({ auth: state, printQRInTerminal: false });
  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      notify('qr', { qr });
    }

    if (connection === 'open') {
      notify('status', { connected: true });
    } else if (connection === 'close') {
      notify('status', { connected: false });
      const statusCode =
        lastDisconnect && lastDisconnect.error && lastDisconnect.error.output
          ? lastDisconnect.error.output.statusCode
          : null;
      const loggedOut = statusCode === DisconnectReason.loggedOut;
      if (!loggedOut) {
        connect().catch((err) => notify('error', { message: String(err) }));
      } else {
        notify('error', { message: 'Logged out of WhatsApp -- delete the auth dir and re-link to reconnect.' });
      }
    }
  });

  sock.ev.on('messages.upsert', ({ messages, type }) => {
    if (type !== 'notify') return;
    for (const m of messages) {
      if (!m.message || m.key.fromMe) continue;
      const text =
        m.message.conversation ||
        (m.message.extendedTextMessage && m.message.extendedTextMessage.text) ||
        '';
      if (!text) continue;
      notify('message', { from: m.key.remoteJid, text });
    }
  });
}

rl.on('line', async (line) => {
  let req;
  try {
    req = JSON.parse(line);
  } catch (err) {
    return; // malformed input is dropped, not fatal -- keeps the sidecar alive
  }

  if (req.method === 'send') {
    try {
      if (!sock) throw new Error('not connected to WhatsApp yet');
      await sock.sendMessage(req.params.to, { text: req.params.text });
      respond(req.id, { ok: true });
    } catch (err) {
      respondError(req.id, err && err.message ? err.message : err);
    }
    return;
  }

  respondError(req.id, `Unknown method: ${req.method}`);
});

connect().catch((err) => {
  notify('error', { message: String(err) });
  process.exit(1);
});
