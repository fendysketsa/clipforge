import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const [, , manifestPath, outputPath] = process.argv;
if (!manifestPath || !outputPath) {
  throw new Error('Usage: node render.mjs <manifest.json> <output.mp4>');
}

const rendererRoot = path.dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(fs.readFileSync(path.resolve(manifestPath), 'utf8'));
const publicDir = path.resolve(manifest.publicDir);
const serveUrl = await bundle({
  entryPoint: path.join(rendererRoot, 'src', 'index.jsx'),
  publicDir,
  onProgress: () => undefined,
});
const inputProps = manifest.composition;
const concurrencyValue = process.env.REMOTION_CONCURRENCY || '25%';
const concurrency = /^\d+$/.test(concurrencyValue)
  ? Number.parseInt(concurrencyValue, 10)
  : concurrencyValue;
const composition = await selectComposition({
  serveUrl,
  id: 'ClipForgeStory',
  inputProps,
  browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE || null,
});
let lastProgress = -1;
await renderMedia({
  serveUrl,
  composition,
  inputProps,
  codec: 'h264',
  pixelFormat: 'yuv420p',
  imageFormat: 'jpeg',
  muted: true,
  outputLocation: path.resolve(outputPath),
  overwrite: true,
  crf: Number.parseInt(process.env.REMOTION_CRF || '17', 10),
  concurrency,
  browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE || null,
  chromiumOptions: {disableWebSecurity: true},
  logLevel: 'warn',
  onProgress: ({progress}) => {
    const value = Math.floor(progress * 100);
    if (value >= lastProgress + 5 || value === 100) {
      lastProgress = value;
      process.stdout.write(`REMOTION_PROGRESS:${value}\n`);
    }
  },
});
process.stdout.write(`REMOTION_OUTPUT:${path.resolve(outputPath)}\n`);
