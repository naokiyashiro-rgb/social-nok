// Renders index.html frame by frame with Playwright and encodes an H.264 MP4 via ffmpeg.
// Usage: node render.mjs [out.mp4] [--stills t1,t2,...]
//   FFMPEG=/path/to/ffmpeg  (defaults to "ffmpeg" on PATH)
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node22/lib/node_modules/playwright'); }

const dir = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const stillsIdx = args.indexOf('--stills');
const stills = stillsIdx >= 0 ? args[stillsIdx + 1].split(',').map(Number) : null;
const out = path.resolve(args.find(a => a.endsWith('.mp4')) ?? path.join(dir, 'experiment-01.mp4'));

const FPS = 30, DURATION = 15, W = 1080, H = 1350;
const FFMPEG = process.env.FFMPEG ?? 'ffmpeg';

const browser = await playwright.chromium.launch();
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.join(dir, 'index.html')).href, { waitUntil: 'networkidle' });
// Web fonts load per unicode-range subset, so request every glyph the video uses up front.
await page.evaluate(async () => {
  for (const w of ['500', '700', '900']) await document.fonts.load(`${w} 100px "Noto Sans JP"`, window.ALL_TEXT);
  for (const w of ['500', '700']) await document.fonts.load(`${w} 100px "JetBrains Mono"`, window.ALL_TEXT);
  await document.fonts.ready;
});

if (stills) {
  const sdir = path.join(dir, 'stills');
  fs.mkdirSync(sdir, { recursive: true });
  for (const t of stills) {
    await page.evaluate(t => window.render(t), t);
    await page.screenshot({ path: path.join(sdir, `t${t.toFixed(2)}.png`) });
  }
  await browser.close();
  process.exit(0);
}

const ff = spawn(FFMPEG, [
  '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-profile:v', 'high', '-pix_fmt', 'yuv420p',
  '-r', String(FPS), '-movflags', '+faststart', out,
], { stdio: ['pipe', 'inherit', 'inherit'] });

const total = FPS * DURATION;
for (let f = 0; f < total; f++) {
  await page.evaluate(t => window.render(t), f / FPS);
  const buf = await page.screenshot({ type: 'png' });
  if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  if (f % 30 === 0) process.stderr.write(`frame ${f}/${total}\n`);
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close();
console.log('wrote', out);
