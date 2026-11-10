import copy,json,urllib.request,re
from pathlib import Path
from playwright.sync_api import sync_playwright
base="http://127.0.0.1:8010"
def get(path):
 with urllib.request.urlopen(base+path,timeout=20) as response:return json.load(response)
job=copy.deepcopy(json.loads(Path('/tmp/upload-submission-fixture.json').read_text()))
job['id']='submission-preview';job['request']['ai_api_key']='';job['source_title']='Pratinjau pemulihan pengiriman lama'
job['clips']=job['clips'][:1];clip=job['clips'][0];clip.update(url='/outputs/submission-preview/clip.mp4',name='clip.mp4',is_correct=True,thumbnail_url=None)
upload=copy.deepcopy(get('/api/youtube/uploads')[0]);upload.update(id='preview-upload',source_job_id=job['id'],clip_url=clip['url'],status='queued',video_url=None,upload_confirmed=False,clip_deleted_at=None,clip_delete_after=None,queue_position=1,queue_total=1,error=None)
configs={f'/api/{platform}/config':get(f'/api/{platform}/config') for platform in ['youtube','tiktok']}
rows=[];calls=[];errors=[];key=f"clipforge:upload-request:youtube:{job['id']}:{clip['url']}"
report={'fixture_only':True,'real_mutations':0}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 context=browser.new_context(viewport={'width':1000,'height':1000},reduced_motion='reduce')
 context.add_init_script('sessionStorage.setItem('+json.dumps(key)+',JSON.stringify({baseline:{}}));')
 def route(intercept):
  req=intercept.request;path=urllib.parse.urlsplit(req.url).path
  if req.method not in ['GET','HEAD']:
   calls.append({'path':path,'method':req.method})
   if path=='/api/jobs/submission-preview/youtube-uploads/reconcile':
    rows[:]=[upload];intercept.fulfill(content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps(upload));return
   intercept.fulfill(status=409,content_type='application/json',body='{"detail":"Unexpected preview mutation blocked"}');return
  data=[job] if path=='/api/jobs' else job if path=='/api/jobs/submission-preview' else rows if path=='/api/youtube/uploads' else [] if path=='/api/tiktok/uploads' else configs.get(path)
  if data is None:
   try:data=get(path)
   except Exception:data={}
  intercept.fulfill(content_type='application/json',headers={'Access-Control-Allow-Origin':'*'},body=json.dumps(data))
 context.route('**/api/**',route)
 page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
 page.goto('http://127.0.0.1:3013/#history',wait_until='networkidle')
 page.locator('.jobRow').first.click()
 button=page.get_by_role('button',name='Kirim YouTube',exact=True);button.wait_for(timeout=15000);button.click()
 page.get_by_text(re.compile('Upload masuk antrean')).first.wait_for(timeout=15000)
 assert len(calls)==1 and calls[0]['path'].endswith('/reconcile'),calls
 assert page.evaluate('key=>sessionStorage.getItem(key)',key) is None
 assert not errors,errors
 folder=Path('reports/upload-submission-recovery-20261110');folder.mkdir(exist_ok=True)
 page.screenshot(path=str(folder/'browser-recovered.png'),full_page=True)
 report.update(legacy_browser_reservation_recovered=True,ordinary_upload_post_count=0,guarded_recovery_count=1,page_errors=errors,calls=calls)
 (folder/'browser-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
 context.close();browser.close()
