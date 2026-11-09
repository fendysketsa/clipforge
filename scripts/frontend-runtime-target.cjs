// Read the running Next server's own directory and production configuration.
// An optional root argument supports local validation without a container.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');

(async () => {
  let root = process.argv[2] ? path.resolve(process.argv[2]) : process.cwd();
  if (!process.argv[2]) {
    for (const pid of fs.readdirSync('/proc').filter((name) => /^\d+$/.test(name))) {
      try {
        const command = fs.readFileSync(`/proc/${pid}/cmdline`, 'utf8');
        if (command.includes('next-server')) {
          root = fs.readlinkSync(`/proc/${pid}/cwd`);
          break;
        }
      } catch { /* Processes may exit while /proc is being read. */ }
    }
  }
  const localRequire = createRequire(path.join(root, 'package.json'));
  const loadConfig = localRequire('next/dist/server/config').default;
  const config = await loadConfig('phase-production-server', root);
  const dist = path.resolve(root, config.distDir || '.next');
  if (!dist.startsWith(root + path.sep)) throw new Error('Build destination must be inside the Next application');
  process.stdout.write('CLIPFORGE_RUNTIME=' + JSON.stringify({ root, dist }) + '\n');
})().catch((error) => { process.stderr.write(error.message + '\n'); process.exitCode = 1; });
