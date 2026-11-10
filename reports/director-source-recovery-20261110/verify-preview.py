import copy,json,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:8010/api/'
def get(path):
 with urllib.request.urlopen(BASE+path,timeout=20) as response:return json.load(response)
fixtures=Path('/tmp/upload-submission-fixture.json')
template=json.loads(fixtures.read_text()) if fixtures.exists() else next(j for j in get('jobs') if j.get('clips'))
titles=['Mio dan Baby Celine: satu keputusan mengubah hasil permainan di Roblox','HIDAYAH MERTUA GALAK — Kamu tidak pantas jadi menantuku! Tapi Akhirnya Menyesal','Misteri angkot biru di Bogor: menyusun konteks dan petunjuk cerita sampai tuntas','Gagal memilih potongan utuh: penjelasan sumber belum memiliki akhir yang jelas','Bukan cuma menang: dua momen kerja sama pemain yang menghasilkan akhir berbeda','Petualangan baru: mencari jalan keluar bersama setelah tersesat di hutan','KISAH HIDUP — Keputusan kecil yang mengubah hubungan keluarga setelah konflik panjang','Cerita reaksi spontan: ketika rencana makan bersama berubah karena pilihan pemain']
statuses=['completed','completed','running','failed','completed','queued','completed','completed']
jobs=[]
for n,(title,status) in enumerate(zip(titles,statuses),1):
 j=copy.deepcopy(template);j.update(id=f'layout-preview-{n}',status=status,source_title=title,source_uploader=['Dunia Budi Roblox','Dongeng Kala','Cerita Nusantara'][n%3],error=None,created_at=f'2026-11-10T00:0{n}:00+00:00',updated_at='2026-11-10T01:00:00+00:00',started_at='2026-11-10T00:01:00+00:00',finished_at='2026-11-10T00:09:00+00:00',duration_seconds=480,progress_percent=76 if status=='running' else 0,progress_detail='Menyusun kalimat utuh dan merender efek sesuai adegan' if status=='running' else 'Menunggu giliran worker berikutnya')
 j['request'].update(ai_api_key='',creator_perspective='Preview fixture',source_rights_evidence='Preview fixture',clip_mode='highlight_5m' if n in (2,7) else 'short',publication_review_required=False)
 j['clips']=j['clips'][:1];j['candidates']=[];j['logs']=[]
 j['clips'][0].update(url=f'/outputs/layout-preview-{n}/video.mp4',thumbnail_url=f'/outputs/layout-preview-{n}.svg',tiktok_upload_issue=None,fyp_score=93-n)
 if status!='completed':j['clips']=[]
 if status=='failed':j['error']='Tidak ditemukan potongan dengan kalimat tuntas dan konteks aman. Sumber dilewati otomatis agar antrean dapat berlanjut.'
 if status=='queued':j['started_at']=None;j['finished_at']=None
 if status=='running':j['finished_at']=None
 if n==5:
  second=copy.deepcopy(j['clips'][0]);second['url']='/outputs/layout-preview-5/second.mp4';j['clips'].append(second)
 if n==7:j['clips'][0]['tiktok_upload_issue']='Menunggu pemeriksaan visual akhir sebelum antrean upload dibuka.'
 if status=='failed':j['director_recovery']={'outcome':'source_replaced','summary':'Alur sumber ini belum layak. Sumber alternatif sudah masuk pipeline.','next_job_id':'layout-preview-3','next_source_title':'Minecraft: mencari tuas rahasia agar bisa keluar rumah'}
 jobs.append(j)
upload_templates={platform:next(x for x in get(platform+'/uploads') if x['status']=='completed') for platform in ('youtube','tiktok')}
def upload(n,platform,status,rank=None,total=None):
 u=copy.deepcopy(upload_templates[platform]);u.update(id=f'{platform}-preview-{n}',source_job_id=jobs[n-1]['id'],clip_url=jobs[n-1]['clips'][0]['url'],status=status,created_at=f'2026-11-10T00:0{n}:00+00:00',updated_at='2026-11-10T01:00:00+00:00',upload_confirmed=status=='completed',queue_position=rank,queue_total=total,clip_deleted_at=None,clip_delete_after=None,clip_cleanup_started_at=None,performance_snapshots=[],video_url='https://youtu.be/previewONLY' if status=='completed' and platform=='youtube' else None,error='Metadata belum dapat diverifikasi; menunggu pemulihan server.' if status=='failed' else None,logs=[])
 return u
yt=[upload(1,'youtube','completed'),upload(2,'youtube','queued',1,2),upload(5,'youtube','completed'),upload(7,'youtube','queued',2,2),upload(8,'youtube','failed')]
tt=[upload(1,'tiktok','queued',1,1),upload(2,'tiktok','running'),upload(5,'tiktok','failed'),upload(8,'tiktok','completed')]
configs={f'/api/{p}/config':get(p+'/config') for p in ('youtube','tiktok')};configs['/api/automation/viral-cc/schedule']=get('automation/viral-cc/schedule')
folder=Path('reports/director-source-recovery-20261110');folder.mkdir(exist_ok=True)
report={'fixture_only':True,'page_errors':[],'mutations_blocked':[],'viewports':[]}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 context=browser.new_context(viewport={'width':1920,'height':1080},reduced_motion='reduce')
 def route(intercept):
  req=intercept.request;path=urlsplit(req.url).path
  if req.method not in ('GET','HEAD'):
   report['mutations_blocked'].append(path);intercept.fulfill(status=409,content_type='application/json',body='{"detail":"Preview is read only"}');return
  data=jobs if path=='/api/jobs' else yt if path=='/api/youtube/uploads' else tt if path=='/api/tiktok/uploads' else configs.get(path)
  if data is None:
   try:data=get(path.removeprefix('/api/'))
   except Exception:data={}
  intercept.fulfill(content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps(data))
 context.route('**/api/**',route)
 context.route('**/outputs/_automation/upload-status.json',lambda r:r.fulfill(content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body='{"enabled":false,"clips":[]}'))
 def thumbnail(intercept):
  svg='<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><defs><linearGradient id="g"><stop stop-color="#164e46"/><stop offset="1" stop-color="#375b7b"/></linearGradient></defs><rect width="640" height="360" fill="url(#g)"/><circle cx="430" cy="130" r="80" fill="#f2ca83" opacity=".2"/><path d="M0 300L150 140 310 300 460 180 640 320V360H0" fill="#082f2b"/><text x="32" y="64" fill="#dbf8e9" font-family="sans-serif" font-size="24">PRATINJAU VIDEO</text></svg>'
  intercept.fulfill(content_type='image/svg+xml',headers={'Access-Control-Allow-Origin':'*'},body=svg)
 context.route('**/outputs/layout-preview-*.svg',thumbnail)
 page=context.new_page();page.on('pageerror',lambda error:report['page_errors'].append(str(error)))
 page.goto('http://127.0.0.1:3014/#history',wait_until='networkidle',timeout=45000)
 page.locator('.jobRow').last.wait_for(state='visible',timeout=20000)
 page.get_by_text('Antrean 2/2',exact=True).first.wait_for(timeout=15000)
 assert len(page.locator('.jobRow').all())==8
 assert page.locator('.jobDirectorRecovery').count()==1
 assert page.get_by_text('Sumber pengganti diproses',exact=True).is_visible()
 assert page.locator('.jobRow--failed').get_by_text('Minecraft: mencari tuas rahasia agar bisa keluar rumah',exact=True).is_visible()
 for width,height,expected in [(1920,1080,4),(1440,1000,4),(1280,1000,4),(1100,1000,3),(900,1000,2),(390,844,1),(320,840,1)]:
  page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(150)
  page.locator('#history').scroll_into_view_if_needed()
  result=page.evaluate('''() => {const list=document.querySelector('.jobList');const cards=[...list.querySelectorAll('.jobRow')];return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,columns:getComputedStyle(list).gridTemplateColumns.split(' ').length,cardWidths:cards.map(c=>Math.round(c.getBoundingClientRect().width)),cards:cards.length,cardOverflow:cards.some(c=>c.scrollWidth>c.clientWidth+1),titleLines:getComputedStyle(cards[0].querySelector('h3')).webkitLineClamp,smallestAction:Math.min(...[...list.querySelectorAll('.jobSelect,.deleteJobRowButton,.stopJobRowButton')].map(x=>Math.min(x.getBoundingClientRect().width,x.getBoundingClientRect().height)))}}''')
  assert result['columns']==expected,result
  assert result['scrollWidth']<=width and not result['cardOverflow'],result
  assert result['smallestAction']>=24,result
  report['viewports'].append(result)
  page.locator('#workspace-history-panel').screenshot(path=str(folder/f'workspace-{width}.png'))
 assert not report['page_errors'],report['page_errors']
 report['queue_information_present']=page.locator('.jobPlatformQueue').count()>0
 report['status_variants']={state:page.locator('.jobRow--'+state).count() for state in set(statuses)}
 (folder/'browser-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
 context.close();browser.close()
