import assert from 'node:assert/strict';
import test from 'node:test';
import {longAutomationForClip} from '../lib/longAutomation.ts';

const url='/outputs/old/clips/resume_cerita.mp4',day='2026-11-13';
const snapshot=()=>({enabled:true,daily_target:1,auto_qc_private_upload:true,
 attempts:[{day,job_id:'old',status:'queued'},{day,job_id:'new',status:'queued'}],
 qc_reviews:[{status:'reviewed',source_job_id:'old',source_clip_url:url,
  audit:{decision:'DROP_SOURCE',upload_allowed:false}}]});

test('a rejected old clip shows actual replacement progress instead of manual retry',()=>{
 const job={id:'new',status:'running',request:{clip_mode:'highlight_5m'},progress_percent:80,progress_detail:'bagian cerita 6 dari 10'};
 const result=longAutomationForClip(url,snapshot(),[job],day);
 assert.equal(result.hold,true);assert.match(result.reason,/DROP_SOURCE/);
 assert.match(result.next,/80%.*bagian cerita 6 dari 10/);assert.equal(result.replacementId,'new');
});
test('a stale queued attempt alone is never reported as a running render',()=>{
 const result=longAutomationForClip(url,snapshot(),[],day);
 assert.equal(result.replacementId,undefined);assert.doesNotMatch(result.next,/80%|sedang dirender/);
});
test('terminal source holds remain held even after an earlier successful upload',()=>{
 const result=longAutomationForClip(url,snapshot(),[],day);
 assert.equal(result.hold,true);assert.equal(result.decision,'DROP_SOURCE');
});
test('missing or incomplete QC cannot claim PASS_UPLOAD',()=>{
 const state=snapshot();state.qc_reviews[0]={...state.qc_reviews[0],status:'waiting_for_ai_or_evidence',audit:null};
 assert.equal(longAutomationForClip(url,state,[],day).hold,true);
 assert.equal(longAutomationForClip('/outputs/other.mp4',state,[],day),null);
});
test('only explicit PASS_UPLOAD and upload_allowed enables automatic Private phase',()=>{
 const state=snapshot();state.qc_reviews[0].audit={decision:'PASS_UPLOAD',upload_allowed:true};
 const result=longAutomationForClip(url,state,[],day);
 assert.equal(result.hold,false);assert.match(result.next,/Private otomatis/);
 state.qc_reviews[0].audit.upload_allowed=false;
 assert.equal(longAutomationForClip(url,state,[],day).hold,true);
});
test('attempt limit and disabled production are explained without promising immediate work',()=>{
 const state=snapshot();state.attempts.push({day,job_id:'third',status:'failed'});
 assert.match(longAutomationForClip(url,state,[],day).next,/Batas percobaan/);
 state.enabled=false;assert.match(longAutomationForClip(url,state,[],day).next,/nonaktif/);
});
test('a completed replacement advances the old card from render to QC and Private admission',()=>{
 const state=snapshot();
 const job={id:'new',status:'completed',request:{clip_mode:'highlight_5m'}};
 assert.match(longAutomationForClip(url,state,[job],day).next,/selesai dirender.*QC otomatis/);
 state.qc_reviews.push({status:'reviewed',source_job_id:'new',source_clip_url:'/new.mp4',audit:{decision:'PASS_UPLOAD',upload_allowed:true}});
 assert.match(longAutomationForClip(url,state,[job],day).next,/berikutnya lolos QC.*Private otomatis/);
 state.qc_reviews[1].upload_hold='bukti sumber berubah';
 assert.match(longAutomationForClip(url,state,[job],day).next,/ditahan.*bukti sumber berubah/);
});
test('a new review-only Long stays held while its QC record has not been written',()=>{
 const job={id:'new',status:'completed',request:{clip_mode:'highlight_5m',publication_review_required:true},clips:[{url:'/new.mp4'}]};
 const result=longAutomationForClip('/new.mp4',snapshot(),[job],day);
 assert.equal(result.hold,true);assert.match(result.reason,/menunggu hasil QC/);
});
test('an upload hold or worker outage is reflected after a passing QC',()=>{
 const state=snapshot();state.qc_reviews[0].audit={decision:'PASS_UPLOAD',upload_allowed:true};
 state.qc_reviews[0].upload_hold='bukti hak belum lengkap';
 assert.equal(longAutomationForClip(url,state,[],day).hold,true);
 assert.match(longAutomationForClip(url,state,[],day).reason,/hak belum lengkap/);
 delete state.qc_reviews[0].upload_hold;state.qc_reviews[0].youtube_worker_error='ConnectionError';
 assert.match(longAutomationForClip(url,state,[],day).next,/pemulihan worker otomatis/);
});

test('a provider refusal explains application QC without calling it a YouTube transfer failure',()=>{
 const state=snapshot();state.qc_reviews[0].audit.evidence=['AI provider explicitly declined this source during content safety screening; semantic/visual approval is unavailable.'];
 const result=longAutomationForClip(url,state,[],day);
 assert.equal(result.hold,true);assert.equal(result.providerDeclined,true);
 assert.match(result.reason,/QC aplikasi.*pemeriksa AI/);
 assert.doesNotMatch(result.reason,/YouTube menolak|koneksi/);
});

test('the daily Long plan uses the backend attempt cap after replacing rejected sources',()=>{
 const state=snapshot();state.daily_target=2;state.daily_attempt_limit=6;
 state.attempts=Array.from({length:4},(_,i)=>({day,job_id:`failed-${i}`,status:'completed'}));
 assert.match(longAutomationForClip(url,state,[],day).next,/mencari Long pengganti/);
 state.attempts.push({day,job_id:'fifth'},{day,job_id:'sixth'});
 assert.match(longAutomationForClip(url,state,[],day).next,/Batas percobaan/);
});

test('confirmed replacement stays visible after artifact cleanup without approving the old source',()=>{
 const state=snapshot();state.attempts[1]={day,job_id:'new',status:'completed',confirmed_upload_id:'record',confirmed_video_url:'https://www.youtube.com/watch?v=2PRl4z8aSx4'};
 const result=longAutomationForClip(url,state,[],day);
 assert.equal(result.hold,true);assert.match(result.next,/sudah terunggah/);
 assert.equal(result.replacementVideoUrl,state.attempts[1].confirmed_video_url);
 delete state.attempts[1].confirmed_upload_id;
 assert.equal(longAutomationForClip(url,state,[],day).replacementVideoUrl,undefined);
 state.attempts[1].confirmed_upload_id='record';state.attempts[1].confirmed_video_url='https://example.test/other';
 assert.equal(longAutomationForClip(url,state,[],day).replacementVideoUrl,undefined);
});
