// Audited Motlab 0.3.0 renderer. One canvas clock keeps captions outside picture transitions.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {renderVideo} from './node_modules/@motlab/cli/src/render.js';

const root = path.dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'node_modules/@motlab/cli/package.json')));
if (Number(process.versions.node.split('.')[0]) < 24 || pkg.version !== '0.3.0') {
  throw new Error('ClipForge Motlab requires Node >=24 and audited @motlab/cli 0.3.0');
}
if (process.argv[2] === '--check') {
  console.log('MOTLAB_READY:0.3.0');
} else {
  const [, , page, output] = process.argv;
  if (!page || !output) throw new Error('Usage: node render.mjs <film.html> <output.mp4>');
  const controller = new AbortController();
  const stop = () => {
    controller.abort(new Error('Motlab render cancelled or timed out'));
    setTimeout(() => process.exit(1), 10000).unref();
  };
  process.once('SIGTERM', stop);process.once('SIGINT', stop);
  const started = Date.now();
  const heartbeat = setInterval(() => console.log('MOTLAB_HEARTBEAT:' + Math.round((Date.now()-started)/1000)), 10000);
  const timeout = setTimeout(stop,
    Math.max(30, Number(process.env.LONG_ANIMATE_MOTLAB_TIMEOUT_SECONDS || 7200)) * 1000);
  try {
    await renderVideo({page: path.resolve(page), out: path.resolve(output),
      fps: 30, scale: 1, workers: 1, encoder: 'sw', codec: 'h264',
      qp: Number(process.env.MOTLAB_QP || 18), chrome: process.env.CHROME,
      signal: controller.signal,
      log: (message) => console.log('MOTLAB_RENDER:' + message)});
    console.log('MOTLAB_OUTPUT:' + path.resolve(output));
  } finally {
    clearTimeout(timeout);
    clearInterval(heartbeat);
  }
}
