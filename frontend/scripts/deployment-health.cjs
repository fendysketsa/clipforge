// Build and runtime verification for the standard Compose deployment.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const requiredJS = ['jobDirectorRecovery', 'history-four-columns', 'jobPlatformQueue', '/reconcile',
  'dijadwalkan ulang otomatis', 'pengaturan privasi tertunda', 'Hasil posting perlu diperiksa',
  'cronActivityHeading', 'Detail pemeriksaan', 'cronDailyLanes',
  'studioSidebar', 'studioQueueRow', 'connectionCard', 'studioThemeToggle'];
const grid = /\.outputWorkspacePane\s+\.jobList\s*\{[^}]*grid-template-columns\s*:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/;
const resultGrid = /\.clipGrid\s*\{[^}]*grid-template-columns\s*:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/;
function walk(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, {withFileTypes:true}).flatMap(entry => {
    const file = path.join(dir, entry.name);
    return entry.isDirectory() ? walk(file) : entry.isFile() ? [file] : [];
  });
}
function sourceFingerprint(base) {
  const files = ['package.json', 'package-lock.json', 'next.config.ts', 'tsconfig.json', 'docker-entrypoint.sh', 'Dockerfile',
    ...['app', 'lib', 'types', 'scripts', 'public'].flatMap(dir => walk(path.join(base, dir)).map(file=>path.relative(base,file)))]
    .filter(file => file !== 'public/deployment.json');
  return Object.fromEntries(files.sort().map(file => [file, digest(fs.readFileSync(path.join(base,file)))]));
}
function build() {
  const dist = process.env.CLIPFORGE_BUILD_DIR || '.next';
  const files = walk(path.join(root,dist,'static'));
  const js = files.filter(file=>file.endsWith('.js')).map(file=>fs.readFileSync(file,'utf8')).join('\n');
  const css = files.filter(file=>file.endsWith('.css')).map(file=>fs.readFileSync(file,'utf8')).join('\n');
  if (!requiredJS.every(text=>js.includes(text)) || !grid.test(css) || !resultGrid.test(css) || !css.includes('[data-theme=light]') || js.includes('Loop belajar YouTube')) throw Error('Built UI lacks current studio theme/cards/upload recovery');
  const sources = sourceFingerprint(root);
  const manifest = {schema:1, dist, build_id:fs.readFileSync(path.join(root,dist,'BUILD_ID'),'utf8').trim(),
    release_id:digest(JSON.stringify(sources)),sources,
    assets:Object.fromEntries(files.map(file=>[path.relative(root,file),digest(fs.readFileSync(file))]))};
  fs.writeFileSync(path.join(root,'deployment-manifest.json'),JSON.stringify(manifest));
  fs.writeFileSync(path.join(root,'public/deployment.json'),JSON.stringify({schema:1,build_id:manifest.build_id,release_id:manifest.release_id,ui_verified:true}));
  console.log(`Frontend build verified: ${manifest.build_id}`);
}
function prepare() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root,'deployment-manifest.json'),'utf8'));
  if (fs.readFileSync(path.join(root,manifest.dist,'BUILD_ID'),'utf8').trim() !== manifest.build_id) throw Error('Mixed frontend build IDs');
  const base = process.env.CLIPFORGE_VERIFY_SOURCE_DIR;
  if (base && JSON.stringify(sourceFingerprint(base)) !== JSON.stringify(manifest.sources)) throw Error('Frontend source changed during build; rerun the same Compose command');
  for (const [file,sha] of Object.entries(manifest.assets)) {
    if (digest(fs.readFileSync(path.join(root,file))) !== sha) throw Error(`Frontend image asset mismatch: ${file}`);
  }
  console.log(`Frontend runtime verified: ${manifest.build_id}`);
}
async function read(url) {
  const response = await fetch(url,{signal:AbortSignal.timeout(2500)});
  if(!response.ok) throw Error(`Frontend readiness HTTP ${response.status}`);
  return response.text();
}
async function health() {
  const manifest = JSON.parse(fs.readFileSync(path.join(root,'deployment-manifest.json'),'utf8'));
  const base = process.env.CLIPFORGE_FRONTEND_HEALTH_BASE || 'http://127.0.0.1:3000';
  const html = await read(base+'/');
  const served = JSON.parse(await read(base+'/deployment.json'));
  if (served.build_id !== manifest.build_id || served.release_id !== manifest.release_id) throw Error('Served frontend release mismatch');
  const urls = [...new Set([...html.matchAll(/(?:src|href)="([^" ]+)"/g)].map(m=>m[1].replaceAll('&amp;','&'))
    .filter(url=>url.startsWith('/_next/static/') && /\.(js|css)(\?|$)/.test(url)))];
  let js='',css='';
  for(const url of urls) {
    const name=new URL(url,base).pathname.replace('/_next/',manifest.dist+'/');
    const body=await read(base+url);
    if(!manifest.assets[name] || digest(body)!==manifest.assets[name]) throw Error('Served assets differ from built frontend');
    if(name.endsWith('.js')) js+=body; else css+=body;
  }
  if(!requiredJS.every(text=>js.includes(text)) || !grid.test(css) || !resultGrid.test(css) || !css.includes('[data-theme=light]')) throw Error('Served frontend is incomplete');
  console.log(`Frontend healthy: ${manifest.build_id}`);
}
if(require.main===module) Promise.resolve().then(()=>({build,prepare,health})[process.argv[2]]()).catch(error=>{console.error(error.message);process.exitCode=1});
module.exports={sourceFingerprint,build,prepare,health};
