#!/usr/bin/env node
// Batch browser flows + screenshots + pixel diff against reference/ui. One browser, one context per account.
// usage: node scripts/shots.mjs [--phase P2] [--only a,b] [--dry-run]
// Pixel diff is a triage signal only; it does not prove visual correctness.
import { createHmac } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = process.env.WF_ROOT || resolve(dirname(fileURLToPath(import.meta.url)), '..');
const cfg = JSON.parse(readFileSync(join(ROOT, 'config/workflow.json'), 'utf8')).shots;
const arg = (k) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null; };
const dry = process.argv.includes('--dry-run');
const phase = arg('--phase');
const only = arg('--only')?.split(',');

export function base32(s) {
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of s.replace(/=+$/, '').toUpperCase()) {
    const v = A.indexOf(c);
    if (v < 0) throw new Error(`bad base32 ${c}`);
    bits += v.toString(2).padStart(5, '0');
  }
  return Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
}

export function totp(secret, t = Date.now(), step = 30, digits = 6) {
  const ctr = Buffer.alloc(8);
  ctr.writeBigUInt64BE(BigInt(Math.floor(t / 1000 / step)));
  const h = createHmac('sha1', base32(secret)).update(ctr).digest();
  const o = h[h.length - 1] & 15;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 10 ** digits).padStart(digits, '0');
}

function accounts() {
  const seed = JSON.parse(readFileSync(join(ROOT, cfg.seed), 'utf8'));
  const t = Object.values(seed).find((v) => v.columns?.includes('demo_password'));
  const col = (r, n) => r[t.columns.indexOf(n)];
  return Object.fromEntries(t.rows.map((r) => [col(r, 'emp_no'), { password: col(r, 'demo_password'), secret: col(r, 'totp_secret') }]));
}

function loadFlows() {
  const p = join(ROOT, cfg.flows);
  if (!existsSync(p)) throw new Error(`${cfg.flows} 없음: 화면 단계에서 흐름을 작성한다`);
  const spec = JSON.parse(readFileSync(p, 'utf8'));
  const flows = spec.flows.filter((f) => (!phase || f.phase === phase) && (!only || only.includes(f.name)));
  for (const f of flows) {
    if (!f.name || !Array.isArray(f.steps)) throw new Error(`flow에 name/steps가 없다: ${JSON.stringify(f).slice(0, 80)}`);
    if (f.ref && !existsSync(join(ROOT, cfg.refs, f.ref))) throw new Error(`${f.name}: 기준 이미지 ${f.ref} 없음`);
  }
  return { auth: spec.auth || {}, flows };
}

async function login(context, page, empNo, acc, auth) {
  const a = acc[empNo];
  if (!a) throw new Error(`시드에 계정 ${empNo} 없음`);
  const req = context.request;
  let r = await req.post(`${cfg.base_url}/api/auth/login`, { data: { emp_no: empNo, password: a.password } });
  let body = await r.json();
  if (!r.ok()) throw new Error(`login ${empNo} ${r.status()} ${JSON.stringify(body).slice(0, 120)}`);
  if (body.otp_required) {
    r = await req.post(`${cfg.base_url}/api/auth/otp/verify`, { data: { code: totp(a.secret) }, headers: { Authorization: `Bearer ${body.otp_token}` } });
    body = await r.json();
    if (!r.ok()) throw new Error(`otp ${empNo} ${r.status()}`);
  }
  if (!auth.key) throw new Error('state/shots.json auth.key(토큰 저장 키)가 없다');
  await page.goto(cfg.base_url);
  await page.evaluate(([s, k, v]) => window[s].setItem(k, v), [auth.storage || 'sessionStorage', auth.key, body.access_token]);
}

// 기능 소개 GIF용 프레임(명세 외 요청): frame 단계마다 <out>/frames/<flow>/NN.png와 캡션을 남긴다.
const rec = { flow: null, n: 0, captions: [], mouse: { x: 0, y: 0 } };
const CURSOR_JS = `(() => { if (window.__cur) return; const d = document.createElement('div'); window.__cur = d;
  d.style.cssText = 'position:fixed;z-index:99999;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;' +
    'background:rgba(239,68,68,.55);border:2px solid #fff;box-shadow:0 0 0 2px rgba(239,68,68,.6);pointer-events:none;left:-50px;top:-50px;transition:transform .1s';
  document.body.appendChild(d);
  addEventListener('mousemove', (e) => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => { d.style.transform = 'scale(.7)'; }, true);
  addEventListener('mouseup', () => { d.style.transform = ''; }, true); })()`;

async function runStep(page, s, timeout) {
  const [op] = Object.keys(s);
  const v = s[op];
  switch (op) {
    case 'goto': return page.goto(cfg.base_url + v);
    case 'click': return page.locator(v).first().click({ timeout });
    case 'fill': return page.locator(v[0]).first().fill(String(v[1]), { timeout });
    case 'press': return page.locator(v[0]).first().press(v[1], { timeout });
    case 'select': return page.locator(v[0]).first().selectOption(String(v[1]), { timeout });
    case 'wait': return typeof v === 'number' ? page.waitForTimeout(v) : page.locator(v).first().waitFor({ timeout });
    case 'hover': return page.locator(v).first().hover({ timeout });
    case 'drag': { // [selector, dx, offsetX?] — 요소 안 offsetX(음수면 오른쪽 끝 기준, 기본 가운데)에서 잡고 가로로 dx px 끈다.
      const box = await page.locator(v[0]).first().boundingBox({ timeout });
      const off = v[2] ?? box.width / 2, x = box.x + (off < 0 ? box.width + off : off), y = box.y + box.height / 2;
      await page.mouse.move(x, y); await page.mouse.down();
      for (let i = 1; i <= 8; i++) await page.mouse.move(x + (v[1] * i) / 8, y);
      return page.mouse.up();
    }
    case 'cursor': return page.evaluate(CURSOR_JS);
    case 'frame': { // v: 캡션
      const dir = join(ROOT, cfg.out, 'frames', rec.flow); mkdirSync(dir, { recursive: true });
      await page.waitForTimeout(120);
      await page.screenshot({ path: join(dir, `${String(rec.n).padStart(2, '0')}.png`) });
      rec.captions.push(v); rec.n++;
      return writeFileSync(join(dir, 'captions.json'), JSON.stringify(rec.captions, null, 1));
    }
    case 'mouseTo': { // [selector, offsetX?] — 요소 위로 커서 이동(offsetX 음수면 오른쪽 끝 기준)
      const box = await page.locator(v[0]).first().boundingBox({ timeout });
      const off = v[1] ?? box.width / 2;
      rec.mouse = { x: box.x + (off < 0 ? box.width + off : off), y: box.y + box.height / 2 };
      return page.mouse.move(rec.mouse.x, rec.mouse.y, { steps: 6 });
    }
    case 'mouseDown': return page.mouse.down();
    case 'mouseBy': rec.mouse.x += v; return page.mouse.move(rec.mouse.x, rec.mouse.y, { steps: 8 });
    case 'mouseUp': return page.mouse.up();
    case 'expect': return page.getByText(v).first().waitFor({ timeout });
    case 'expectNot': return page.getByText(v).first().waitFor({ state: 'hidden', timeout });
    default: throw new Error(`unknown step ${op}`);
  }
}

async function diff(browser, shotPng, refPng, tol) {
  const page = await browser.newPage();
  try {
    return await page.evaluate(async ([a, b, tol]) => {
      const img = (src) => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });
      const [A, B] = await Promise.all([img(a), img(b)]);
      const w = B.naturalWidth, h = B.naturalHeight;
      const ctx = (im) => { const c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'); x.drawImage(im, 0, 0, w, h); return [c, x]; };
      const [, xa] = ctx(A); const [cb, xb] = ctx(B);
      const da = xa.getImageData(0, 0, w, h), db = xb.getImageData(0, 0, w, h);
      let n = 0;
      for (let i = 0; i < da.data.length; i += 4) {
        const d = Math.max(Math.abs(da.data[i] - db.data[i]), Math.abs(da.data[i + 1] - db.data[i + 1]), Math.abs(da.data[i + 2] - db.data[i + 2]));
        const g = (db.data[i] + db.data[i + 1] + db.data[i + 2]) / 3 * 0.35 + 160;
        if (d > tol) { n++; db.data[i] = 255; db.data[i + 1] = 0; db.data[i + 2] = 0; } else { db.data[i] = db.data[i + 1] = db.data[i + 2] = g; }
      }
      xb.putImageData(db, 0, 0);
      return { ratio: n / (w * h), sizeMatch: A.naturalWidth === w && A.naturalHeight === h, size: [A.naturalWidth, A.naturalHeight], diffPng: cb.toDataURL('image/png') };
    }, [`data:image/png;base64,${shotPng.toString('base64')}`, `data:image/png;base64,${refPng.toString('base64')}`, tol]);
  } finally { await page.close(); }
}

async function main() {
  const { auth, flows } = loadFlows();
  const acc = accounts();
  if (dry) {
    for (const f of flows) console.log(`DRY ${f.name} account=${f.account || '-'} steps=${f.steps.length} ref=${f.ref || '-'}`);
    for (const [k, a] of Object.entries(acc)) if (a.secret) console.log(`totp ${k} ${totp(a.secret).replace(/./g, '#')} (ok)`);
    console.log(`flows=${flows.length} (dry-run, browser not started)`);
    return 0;
  }
  if (!flows.length) { console.log('실행할 flow가 없다'); return 1; }
  let chromium;
  try { ({ chromium } = await import('playwright-core')); } catch { console.log('playwright-core 없음: npm install --prefix scripts'); return 1; }
  const out = join(ROOT, cfg.out); mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: cfg.browser_channel, headless: true });
  const results = [];
  const groups = new Map();
  for (const f of flows) { const k = `${f.account || ''}|${(f.viewport || cfg.default_viewport).join('x')}`; groups.set(k, [...(groups.get(k) || []), f]); }
  try {
    for (const [key, group] of groups) {
      const [account, vp] = key.split('|');
      const [width, height] = vp.split('x').map(Number);
      const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce' });
      const page = await context.newPage();
      const consoleErrors = [];
      page.on('pageerror', (e) => consoleErrors.push(String(e).slice(0, 160)));
      page.on('dialog', (d) => d.accept());
      try {
        if (account) await login(context, page, account, acc, auth);
      } catch (e) {
        for (const f of group) results.push({ name: f.name, status: 'error', error: String(e.message).slice(0, 200) });
        await context.close(); continue;
      }
      for (const f of group) {
        const r = { name: f.name, phase: f.phase, ref: f.ref || null };
        Object.assign(rec, { flow: f.name, n: 0, captions: [] });
        consoleErrors.length = 0;
        try {
          for (const s of f.steps) await runStep(page, s, cfg.step_timeout_ms);
          const file = join(out, `${f.name}.png`);
          const target = f.clip ? page.locator(f.clip).first() : page;
          const png = await target.screenshot({ path: file, animations: 'disabled' });
          r.file = `${cfg.out}/${f.name}.png`;
          if (f.ref) {
            const d = await diff(browser, png, readFileSync(join(ROOT, cfg.refs, f.ref)), cfg.pixel_tolerance);
            writeFileSync(join(out, `${f.name}.diff.png`), Buffer.from(d.diffPng.split(',')[1], 'base64'));
            const th = f.threshold ?? cfg.threshold;
            Object.assign(r, { diff: +d.ratio.toFixed(4), threshold: th, sizeMatch: d.sizeMatch, status: d.ratio <= th && d.sizeMatch ? 'ok' : 'over' });
            if (!d.sizeMatch) r.note = `size ${d.size.join('x')} != ref`;
          } else r.status = 'pass';
        } catch (e) {
          r.status = 'error'; r.error = String(e.message).split('\n')[0].slice(0, 200);
          await page.screenshot({ path: join(out, `${f.name}.error.png`) }).catch(() => {});
        }
        if (consoleErrors.length) r.pageErrors = consoleErrors.slice(0, 3);
        results.push(r);
      }
      await context.close();
    }
  } finally { await browser.close(); }
  const ok = results.every((r) => r.status === 'ok' || r.status === 'pass');
  const phases = [...new Set(flows.map((f) => f.phase).filter(Boolean))];
  writeFileSync(join(ROOT, 'state/shots-result.json'), JSON.stringify({ ts: new Date().toISOString().replace('Z', '+00:00'), ok, phases, results }, null, 2));
  for (const r of results) console.log(`${r.status.padEnd(5)} ${r.name}${r.diff !== undefined ? ` diff=${r.diff}/${r.threshold}` : ''}${r.note ? ` ${r.note}` : ''}${r.error ? ` ${r.error}` : ''}${r.pageErrors ? ` pageErrors=${r.pageErrors.length}` : ''}`);
  console.log(`shots ${ok ? 'OK' : 'CHECK'}: ${results.length} flows, 기준 초과·오류만 ${cfg.out}/<name>.png 와 .diff.png 를 본다`);
  return ok ? 0 : 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then((c) => process.exit(c), (e) => { console.log(`shots ERROR: ${e.message}`); process.exit(1); });
}
