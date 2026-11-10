"""Read-only exact-ID audit; own tabs only; no save, post, transfer or cookie write."""
from pathlib import Path
import json,re,time
from playwright.sync_api import sync_playwright

root=Path(__file__).resolve().parent
rows=json.loads((root/'youtube-before.json').read_text())
tiktok=json.loads((root/'tiktok-before.json').read_text())
report={'read_only':True,'youtube':[],'tiktok':{},'no_upload_or_post':True}
with sync_playwright() as p:
 b=p.chromium.connect_over_cdp('http://127.0.0.1:9333',timeout=15000)
 c=b.contexts[0]
 for row in rows:
  vid=re.search(r'[?&]v=([\w-]+)',row.get('video_url') or '')
  if not vid:continue
  page=c.new_page()
  result={'upload_id':row['id'],'video_id':vid[1]}
  try:
   page.goto('https://studio.youtube.com/video/'+vid[1]+'/edit',wait_until='domcontentloaded',timeout=25000)
   page.locator('ytcp-video-metadata-editor').wait_for(state='attached',timeout=15000)
   text=page.locator('body').inner_text(timeout=5000)
   fields=[]
   for textbox in page.locator('[contenteditable="true"]').all():
    if textbox.is_visible():fields.append(textbox.inner_text(timeout=1000)[:200])
   result.update(url=page.url,visible_fields=fields[:3],
     status_markers=[phrase for phrase in ['Publik','Public','Pribadi','Private','Dijadwalkan','Scheduled','Draf','Draft','Video tidak ditemukan','Video ini telah dihapus','Maaf, ada yang tidak beres'] if phrase in text],
     title_matches=bool(row.get('title') and row['title'].casefold() in text.casefold()))
  except Exception as e:result['error']=type(e).__name__+': '+str(e).splitlines()[0][:150]
  finally:page.close()
  report['youtube'].append(result)
 page=c.new_page()
 try:
  page.goto('https://www.tiktok.com/tiktokstudio/content',wait_until='domcontentloaded',timeout=25000)
  page.locator('body').wait_for(state='visible',timeout=5000)
  text=''
  for _ in range(12):
   text=page.locator('body').inner_text(timeout=3000)
   if len(text)>400:break
   page.wait_for_timeout(1000)
  matches=[]
  for row in tiktok:
   caption=' '.join((row.get('caption') or '').split()).split('#',1)[0][:100]
   if not caption:continue
   matched=caption.casefold() in ' '.join(text.split()).casefold()
   matches.append({'upload_id':row['id'],'caption_prefix':caption,'found_on_first_content_page':matched,'submission_started':row.get('submission_started')})
  report['tiktok']={'url':page.url,'visible_video_ids':sorted(set(re.findall(r'/video/(\d+)',page.content()))),
    'caption_matches':matches,'login_required':bool(re.search(r'Log in to TikTok|Masuk ke TikTok',text,re.I)),
    'note':'Absence on one page does not prove no post; unknown submission remains held.'}
 except Exception as e:report['tiktok']={'error':type(e).__name__+': '+str(e).splitlines()[0][:150]}
 finally:page.close()
(root/'remote-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
