import json,urllib.request,copy
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
base='http://127.0.0.1:8010/api/'
with urllib.request.urlopen(base+'jobs',timeout=15) as response:live=json.load(response)
template=next((j for j in live if j.get('clips')), live[0] if live else dict(request={},clips=[],logs=[],candidates=[],created_at='2026-11-10T00:00:00+00:00',updated_at='2026-11-10T00:00:00+00:00',error=None))
if not template.get('clips'): template['clips']=[dict(name='preview.mp4',url='/outputs/preview.mp4',size_bytes=1000000,thumbnail_url=None,fyp_score=93,is_correct=True)]
template['request'].update(crop_mode='person',video_quality='high',ai_enabled=True,ai_model='llama3.2-id:latest',url='https://www.youtube.com/watch?v=previewONLY')
titles=['Mio dan Baby Celine: keputusan pemain mengubah jalannya cerita di Roblox','HIDAYAH MERTUA GALAK — Kamu tidak pantas jadi menantuku! Tapi Akhirnya Menyesal','KISAH VIRAL DI BOGOR! URBAN LEGEND ANGKOT BIRU GAIB, SEMUA PENUMPANG SUDAH MENINGGAL']
jobs=[]
for index,title in enumerate(titles,1):
 j=copy.deepcopy(template);j.update(id=f'queue-preview-{index}',status='completed',source_title=title,source_uploader='Pratinjau antrean',created_at=f'2026-11-10T00:0{index}:00+00:00');j['request']['ai_api_key']='';j['request']['clip_mode']='highlight_5m';j['request']['publication_review_required']=False
 j['clips']=j['clips'][:1];j['clips'][0].update(url=f'/outputs/queue-preview-{index}/video.mp4',tiktok_upload_issue=None);jobs.append(j)
upload_templates={}
for platform in ('youtube','tiktok'):
 with urllib.request.urlopen(base+platform+'/uploads',timeout=15) as response: rows=json.load(response)
 upload_templates[platform]=next((x for x in rows if x.get('status')=='completed'),rows[0] if rows else {})
def upload(index,platform,status,position=None,total=None):
 result=copy.deepcopy(upload_templates[platform])
 result.update(dict(id=f'preview-{platform}-{index}',source_job_id=jobs[index-1]['id'],clip_url=jobs[index-1]['clips'][0]['url'],clip_name='video.mp4',title=titles[index-1],caption=titles[index-1],status=status,created_at=f'2026-11-10T00:0{index}:00+00:00',updated_at='2026-11-10T01:00:00+00:00',queue_position=position,queue_total=total,description='Pratinjau metadata',tags=[],playlist='',target_channel='',series_label='Pratinjau',target_handle='',target_email='',performance_snapshots=[],metrics_to_track=[],logs=[],upload_confirmed=False,dry_run=False,visibility='private' if platform=='youtube' else 'only_you',clip_deleted_at=None,clip_delete_after=None,clip_cleanup_started_at=None,video_url=None,profile_url=None,error=None))
 return result
yt=[upload(1,'youtube','running'),upload(2,'youtube','queued',1,2),upload(3,'youtube','queued',2,2)]
tt=[upload(i,'tiktok','queued',i,3) for i in (1,2,3)]
configs={}
for platform in ('youtube','tiktok'):
 with urllib.request.urlopen(base+platform+'/config',timeout=15) as response:configs['/api/'+platform+'/config']=json.load(response)
report={'fixture_only':True,'mutations_blocked':[],'viewports':[],'page_errors':[]}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 context=browser.new_context(viewport={'width':1920,'height':1080},reduced_motion='reduce')
 def route(request_route):
  req=request_route.request;path=urlsplit(req.url).path
  if path=='/api/youtube/uploads':print('YT_REQUEST',[(x['status'],x['queue_position']) for x in yt],flush=True)
  if req.method not in ('GET','HEAD'):
   report['mutations_blocked'].append(path);request_route.fulfill(status=409,content_type='application/json',body='{"detail":"Preview is read-only"}');return
  data=jobs if path=='/api/jobs' else yt if path=='/api/youtube/uploads' else tt if path=='/api/tiktok/uploads' else configs.get(path)
  if data is not None:request_route.fulfill(content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps(data))
  else:request_route.continue_()
 context.route('**/api/**',route)
 page=context.new_page();page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
 page.goto('http://127.0.0.1:3012/#history',wait_until='networkidle',timeout=45000)
 page.locator('.jobRow').first.wait_for(state='visible',timeout=20000)
 print('LABELS',page.locator('.jobPlatformStatuses').all_text_contents(),flush=True)
 page.get_by_text('Antrean 3/3',exact=True).first.wait_for(timeout=15000)
 report['initial_labels']=page.locator('.jobPlatformStatus').all_text_contents()
 assert any('Mengunggah' in value and '1/3' in value for value in report['initial_labels'])
 assert any('2 video di depan' in value for value in report['initial_labels'])
 page.screenshot(path='reports/upload-queue-ui-20261110/desktop-1920.png',full_page=True)
 yt[:]=[upload(1,'youtube','completed'),upload(2,'youtube','running'),upload(3,'youtube','queued',1,1)]
 yt[0]['upload_confirmed']=True;yt[0]['video_url']='https://www.youtube.com/watch?v=previewONLY'
 print('HIDDEN',page.evaluate('document.hidden'),flush=True)
 page.evaluate("window.dispatchEvent(new Event('focus'))")
 page.wait_for_timeout(1000)
 print('UPDATED_LABELS',page.locator('.jobPlatformStatuses').all_text_contents(),'ERRORS',report['page_errors'],flush=True)
 page.screenshot(path='reports/upload-queue-ui-20261110/debug-updated.png',full_page=True)
 page.get_by_text('Antrean 2/2',exact=True).wait_for(timeout=20000)
 report['queue_advanced_without_reload']=True
 for width,height in [(1920,1080),(1280,1000),(390,844),(320,840)]:
  page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(250)
  metrics=page.evaluate('''() => {const list=document.querySelector('.jobList');return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,columns:getComputedStyle(list).gridTemplateColumns.split(' ').length,cards:document.querySelectorAll('.jobRow').length}}''')
  assert metrics['scrollWidth']<=width,metrics
  assert metrics['columns']==(3 if width>=1280 else 1),metrics
  report['viewports'].append(metrics)
  if width!=1920:page.screenshot(path=f'reports/upload-queue-ui-20261110/viewport-{width}.png',full_page=True)
 assert not report['page_errors'],report['page_errors']
 Path('reports/upload-queue-ui-20261110/browser-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
 context.close();browser.close()
