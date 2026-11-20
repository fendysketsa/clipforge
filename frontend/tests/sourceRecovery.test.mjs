import test from 'node:test';
import assert from 'node:assert/strict';
import { sourceRecoveryForJob } from '../lib/sourceRecovery.ts';

const old={id:'old',status:'failed',clips:[],candidates:[],created_at:'2026-11-20T01:00:00Z',updated_at:'2026-11-20T01:01:00Z',
  error:'Koneksi server ke YouTube gagal saat mengunduh video.',request:{url:'https://youtu.be/abcdefghijk',clip_mode:'short',target_platform:'standard'}};
const active={...old,id:'new',status:'running',created_at:'2026-11-20T02:00:00Z',error:null};

test('a later active job on the exact source is shown as recovery, not a second permanent outage',()=>{
  assert.equal(sourceRecoveryForJob(old,[old,active]).id,'new');
  assert.equal(sourceRecoveryForJob(old,[old,{...active,request:{...active.request,url:'https://www.youtube.com/watch?v=abcdefghijk'}}]).id,'new');
});
test('completion needs real results and never grants publication approval',()=>{
  assert.equal(sourceRecoveryForJob(old,[{...active,status:'completed',clips:[]}]),null);
  assert.equal(sourceRecoveryForJob(old,[{...active,status:'completed',clips:[{url:'/outputs/held.mp4',youtube_upload_ready:false}]}]).id,'new');
});
test('other sources, earlier attempts, formats, and platforms do not hide a failure',()=>{
  for(const changed of [
    {...active,request:{...active.request,url:'https://youtu.be/lmnopqrstuv'}},
    {...active,request:{...active.request,clip_mode:'highlight_5m'}},
    {...active,request:{...active.request,target_platform:'facebook'}},
    {...active,created_at:'2026-11-20T00:59:00Z'},
    {...active,status:'failed'},
  ]) assert.equal(sourceRecoveryForJob(old,[changed]),null);
});
test('QC, publication holds, and analysis-only jobs remain explicit',()=>{
  assert.equal(sourceRecoveryForJob({...old,error:'QC menolak sumber'},[active]),null);
  assert.equal(sourceRecoveryForJob({...old,error:'QC menolak sumber',download_diagnostics:{transport_failure:true,recovered:true}},[active]),null);
  assert.equal(sourceRecoveryForJob({...old,request:{...old.request,publication_review_required:true}},[active]),null);
  assert.equal(sourceRecoveryForJob(old,[{...active,request:{...active.request,review_only:true}}]),null);
});
test('source URL lookalikes and invalid timestamps cannot create a recovery link',()=>{
  assert.equal(sourceRecoveryForJob(old,[{...active,request:{...active.request,url:'https://youtube.com.attacker.test/watch?v=abcdefghijk'}}]),null);
  assert.equal(sourceRecoveryForJob({...old,updated_at:'invalid'},[active]),null);
});
