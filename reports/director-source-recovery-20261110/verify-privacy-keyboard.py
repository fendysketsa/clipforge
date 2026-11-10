"""Offline moving-button fixture: no account, file transfer or Post action."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import tiktok_uploader as uploader

report={'fixture_only':True,'post_control_present':False,'cases':[]}
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/google-chrome',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 context=browser.new_context(viewport={'width':700,'height':500})
 page=context.new_page()
 for target,current,setter in [('Only you','Everyone',uploader.set_only_you),('Everyone','Only you',uploader.set_public)]:
  page.set_content('''<style>@keyframes moving{from{transform:translateX(0)}to{transform:translateX(100px)}}
button{animation:moving 1s linear infinite;padding:16px;margin:16px}</style>
<button id="privacy" data-e2e="privacy-level" role="combobox" aria-expanded="false"></button>
<button id="option" role="option" hidden></button>''')
  page.evaluate('''({current,target})=>{const trigger=document.querySelector('#privacy'),option=document.querySelector('#option');
window.privacyKeys=[];trigger.onkeydown=event=>window.privacyKeys.push(event.key);option.onkeydown=event=>window.privacyKeys.push(event.key);trigger.textContent=current;option.textContent=target;
trigger.onclick=()=>{option.hidden=false;trigger.setAttribute('aria-expanded','true')};
option.onclick=()=>{trigger.textContent=target;trigger.setAttribute('aria-expanded','false');option.hidden=true};}''',{'current':current,'target':target})
  setter(page)
  selected=page.locator('#privacy').inner_text()
  assert selected==target,(target,selected)
  keys=page.evaluate('window.privacyKeys');assert keys.count('Enter')>=2,keys
  report['cases'].append({'keyboard_keys':keys,'initial':current,'target':target,'selected':selected,'moving_controls':True})
 context.close();browser.close()
Path('reports/director-source-recovery-20261110/privacy-browser-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
