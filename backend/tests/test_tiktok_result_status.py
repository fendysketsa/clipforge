"""Render the real cards offline: unknown Post must never expose a retry."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_tiktok_cards_preserve_submission_history_and_actual_privacy():
    root=Path(__file__).resolve().parents[2]
    if not shutil.which('node') or not (root/'frontend/node_modules/typescript').exists():
        pytest.skip('Frontend build dependencies unavailable')
    script=r'''
const fs=require('fs');
const assert=require('node:assert/strict');
const ts=require('typescript');
for(const ext of ['.ts','.tsx']) require.extensions[ext]=(mod,file)=>{
  mod._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{
    module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,
    target:ts.ScriptTarget.ES2020}}).outputText,file);
};
const React=require('react');
const {renderToStaticMarkup:render}=require('react-dom/server');
global.fetch=()=>{throw Error('UI test must not contact any server')};
const {ResultsSection}=require('./app/_components/ResultsSection.tsx');
const {HistorySection}=require('./app/_components/HistorySection.tsx');
const {tiktokUploadForClip:state}=require('./lib/tiktokRetry.ts');
const clip={name:'clip.mp4',url:'/clip.mp4',size_bytes:100,title:'Judul sesuai sumber',is_correct:true,
  fyp_score:95,growth_quality_gate_passed:true};
const row={id:'new',source_job_id:'source',clip_url:clip.url,target_handle:'owner',clip_sha256:'hash',
  dry_run:false,status:'failed',visibility:'only_you',created_at:'2026-11-11T06:16:00Z',
  logs:[],upload_confirmed:false,error:'Kontrol privasi TikTok belum siap. Video belum diposting.'};
const previous={...row,id:'old',created_at:'2026-11-11T05:16:00Z',submission_accepted:true};
const confirmed={...previous,status:'completed',upload_confirmed:true,
  profile_url:'https://www.tiktok.com/@owner/video/123',visibility:'public'};
assert.equal(state([row,previous],clip.url).uncertain,true);
assert.equal(state([row,confirmed],clip.url).latest.id,'old');
assert.equal(state([row,{...confirmed,clip_sha256:'different'}],clip.url).latest.id,'new');
assert.equal(state([row,{...previous,target_handle:'someone_else'}],clip.url).uncertain,false);
assert.equal(state([row,{...previous,dry_run:true}],clip.url).uncertain,false);
assert.equal(state([row,{...previous,submission_accepted:false,logs:['POST_SUBMIT_INTENT: issued']}],clip.url).uncertain,true);
assert.equal(state([],clip.url).latest,undefined);
const props={clips:[clip],selectedClipUrls:[],youtubeEnabled:true,youtubeStatusMessage:'',youtubeAutoUploadCount:1,
  youtubeUploadAllAboveTarget:false,youtubeUploads:[],tiktokEnabled:true,tiktokStatusMessage:'',tiktokTargetHandle:'owner',
  tiktokAutoUploadCount:1,isTikTokLoginActive:false,isYouTubeLoginActive:false};
const html=render(React.createElement(ResultsSection,{...props,tiktokUploads:[row,previous]}));
assert.match(html,/Hasil posting perlu diperiksa/);
assert.match(html,/<button[^>]*disabled=""[^>]*aria-label="[^"]*Post/);
assert.match(html,/https:\/\/www.tiktok.com\/tiktokstudio\/content/);
assert.doesNotMatch(html,/>Ulangi TikTok</);
const success=render(React.createElement(ResultsSection,{...props,tiktokUploads:[row,confirmed]}));
assert.match(success,/tujuan Everyone/);
assert.match(success,/posting terverifikasi/);
assert.doesNotMatch(success,/tersimpan Only you/);
const prepost=render(React.createElement(ResultsSection,{...props,tiktokUploads:[row]}));
assert.match(prepost,/pengaturan privasi tertunda/);
assert.match(prepost,/Job meminta Only you/);
const historyProps={jobs:[{id:'source',status:'completed',request:{url:'https://youtu.be/example',clip_mode:'short'},
  created_at:'2026-11-11T05:00:00Z',clips:[clip],logs:[]}],youtubeUploads:[],selectedJobIds:[]};
const history=render(React.createElement(HistorySection,{...historyProps,tiktokUploads:[row,previous]}));
assert.match(history,/Periksa hasil Post/);
const historySuccess=render(React.createElement(HistorySection,{...historyProps,tiktokUploads:[row,confirmed]}));
assert.match(historySuccess,/Terupload &amp; terverifikasi/);
console.log('TikTok cards: unknown Post held, confirmed hash reused, privacy truthful.');
'''
    result=subprocess.run(['node','-e',script],cwd=root/'frontend',capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
