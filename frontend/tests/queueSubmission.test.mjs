import assert from 'node:assert/strict';
import test from 'node:test';
import { createQueueSubmitter, uploadApiBases } from '../lib/queueSubmission.ts';

const input = {platform:'youtube',jobId:'job',clipUrl:'/outputs/job/clip.mp4',baseUrl:'http://api.test'};
const row = (overrides={}) => ({id:'accepted',source_job_id:'job',clip_url:input.clipUrl,status:'queued',updated_at:'new',...overrides});
const store = () => {
  const data=new Map();return {data,getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};
};
const message = async response => (await response.json()).detail;
const json = (value,status=200) => new Response(JSON.stringify(value),{status,headers:{'content-type':'application/json'}});

test('lost response reconciles the accepted record with GET without another POST', async () => {
  let rows=[],posts=0;const state=store();
  const fetcher=async (_url,options={})=>{
    if(options.method==='POST'){posts++;rows=[row()];throw new TypeError('Failed to fetch');}
    return json(rows);
  };
  const submit=createQueueSubmitter(fetcher,()=>state,message);
  assert.equal((await submit(input)).id,'accepted');
  assert.equal((await submit(input)).id,'accepted');
  assert.equal(posts,1);assert.equal(state.data.size,0);
});

test('unknown outcome survives reload and cannot replay the ordinary POST on an older backend', async () => {
  let rows=[],posts=0;const state=store();
  const fetcher=async (url,options={})=>{
    if(url.endsWith('/reconcile'))return json({detail:'Not Found'},404);
    if(options.method==='POST'){posts++;throw new TypeError('Failed to fetch');}
    return json(rows);
  };
  await assert.rejects(createQueueSubmitter(fetcher,()=>state,message)(input),/Backend belum mendukung/);
  const reloaded=createQueueSubmitter(fetcher,()=>state,message);
  await assert.rejects(reloaded(input),/Backend belum mendukung/);
  assert.equal(posts,1);
  rows=[row()];assert.equal((await reloaded(input)).id,'accepted');assert.equal(posts,1);
});

test('double clicks share one submission and TikTok preserves Only-you visibility', async () => {
  let posts=0,payload;
  const fetcher=async (_url,options={})=>{
    if(options.method==='POST'){posts++;payload=JSON.parse(options.body);return json(row());}
    return json([]);
  };
  const submit=createQueueSubmitter(fetcher,()=>store(),message);
  const [a,b]=await Promise.all([submit({...input,platform:'tiktok'}),submit({...input,platform:'tiktok'})]);
  assert.equal(posts,1);assert.equal(a.id,b.id);assert.equal(payload.visibility,'only_you');
});

test('manual YouTube review explicitly requests Private for original and recovered admission', async () => {
  const payloads=[];
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(options.method==='POST'){
      payloads.push(JSON.parse(options.body));
      if(!url.endsWith('/reconcile'))throw new TypeError('Lost response');
      return json(row());
    }
    return json([]);
  },()=>store(),message);
  assert.equal((await submit(input)).id,'accepted');
  assert.equal(payloads.length,2);
  assert.ok(payloads.every(payload=>payload.visibility==='private'));
});

test('definite preflight rejection releases its reservation and keeps the backend explanation', async () => {
  let posts=0;const state=store();
  const fetcher=async (_url,options={})=>options.method==='POST'
    ?(posts++,json({detail:'Review konteks diperlukan'},409)):json([]);
  const submit=createQueueSubmitter(fetcher,()=>state,message);
  await assert.rejects(submit(input),/Review konteks diperlukan/);
  assert.equal(state.data.size,0);
  await assert.rejects(submit(input),/Review konteks diperlukan/);assert.equal(posts,2);
});

test('an unchanged older failure cannot falsely reconcile a newer uncertain request', async () => {
  let posts=0;const state=store();
  const fetcher=async (url,options={})=>{
    if(url.endsWith('/reconcile'))throw new TypeError('Offline');
    if(options.method==='POST'){posts++;throw new TypeError('Failed to fetch');}
    return json([row({id:'old',status:'failed',updated_at:'old'})]);
  };
  const submit=createQueueSubmitter(fetcher,()=>state,message);
  await assert.rejects(submit(input),/Layanan upload/);
  await assert.rejects(submit(input),/Layanan upload/);assert.equal(posts,1);
});

test('legacy empty reservations recover through serialized admission without another ordinary POST', async () => {
  const state=store();state.setItem(`clipforge:upload-request:youtube:job:${input.clipUrl}`,JSON.stringify({baseline:{}}));
  let posts=0,recoveries=0;
  const fetcher=async (url,options={})=>{
    if(url.endsWith('/reconcile')){recoveries++;return json(row());}
    if(options.method==='POST'){posts++;throw new Error('Ordinary replay is forbidden');}
    return json([]);
  };
  assert.equal((await createQueueSubmitter(fetcher,()=>state,message)(input)).id,'accepted');
  assert.equal(posts,0);assert.equal(recoveries,1);assert.equal(state.data.size,0);
});

test('a request lost before admission automatically uses guarded recovery once', async () => {
  const state=store();let posts=0,recoveries=0;
  const fetcher=async (url,options={})=>{
    if(url.endsWith('/reconcile')){recoveries++;return json(row());}
    if(options.method==='POST'){posts++;throw new TypeError('Failed to fetch');}
    return json([]);
  };
  assert.equal((await createQueueSubmitter(fetcher,()=>state,message)(input)).status,'queued');
  assert.equal(posts,1);assert.equal(recoveries,1);assert.equal(state.data.size,0);
});

test('recovery exposes actual backend capacity rejection and releases the stale browser guard', async () => {
  const state=store();state.setItem(`clipforge:upload-request:youtube:job:${input.clipUrl}`,JSON.stringify({baseline:{}}));
  const submit=createQueueSubmitter(async url=>url.endsWith('/reconcile')
    ?json({detail:'Cadangan Private dan antrean jadwal cron penuh'},409):json([]),()=>state,message);
  await assert.rejects(submit(input),/antrean jadwal cron penuh/);assert.equal(state.data.size,0);
});

test('recovery cannot accept a mismatched clip or erase its reservation', async () => {
  const state=store();state.setItem(`clipforge:upload-request:youtube:job:${input.clipUrl}`,JSON.stringify({baseline:{}}));
  const submit=createQueueSubmitter(async url=>url.endsWith('/reconcile')
    ?json(row({clip_url:'/outputs/someone-else.mp4'})):json([]),()=>state,message);
  await assert.rejects(submit(input),/Identitas balasan upload/);assert.equal(state.data.size,1);
});

test('a malformed successful response also recovers through guarded admission', async () => {
  let posts=0,recoveries=0;
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(url.endsWith('/reconcile')){recoveries++;return json(row());}
    if(options.method==='POST'){posts++;return json(null);}
    return json([]);
  },()=>store(),message);
  assert.equal((await submit(input)).id,'accepted');assert.equal(posts,1);assert.equal(recoveries,1);
});

test('a backend 500 after acceptance is reconciled without replaying the mutation', async () => {
  let rows=[],posts=0;
  const fetcher=async (_url,options={})=>{
    if(options.method==='POST'){posts++;rows=[row()];return json({detail:'Response failed'},500);}
    return json(rows);
  };
  assert.equal((await createQueueSubmitter(fetcher,()=>store(),message)(input)).id,'accepted');
  assert.equal(posts,1);
});

test('queue connection failure does not submit and does not leak Failed to fetch to the UI', async () => {
  let posts=0;
  const submit=createQueueSubmitter(async (_url,options={})=>{
    if(options.method==='POST')posts++;
    throw new TypeError('Failed to fetch');
  },()=>null,message);
  await assert.rejects(submit(input),/Layanan antrean upload belum dapat dihubungi/);assert.equal(posts,0);
});

test('temporary recovery connection failure retries guarded admission, never the ordinary POST', async () => {
  let posts=0,recoveries=0;const state=store();
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(url.endsWith('/reconcile')) {
      recoveries++;
      if(recoveries===1)throw new TypeError('Connection reset');
      return json(row());
    }
    if(options.method==='POST'){posts++;throw new TypeError('Lost response');}
    return json([]);
  },()=>state,message);
  assert.equal((await submit(input)).id,'accepted');
  assert.equal(posts,1);assert.equal(recoveries,2);assert.equal(state.data.size,0);
});

test('lost recovery response discovers the accepted row before retrying admission', async () => {
  let rows=[],posts=0,recoveries=0;
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(url.endsWith('/reconcile')){recoveries++;rows=[row()];throw new TypeError('Lost response');}
    if(options.method==='POST'){posts++;throw new TypeError('Lost response');}
    return json(rows);
  },()=>store(),message);
  assert.equal((await submit(input)).id,'accepted');assert.equal(posts,1);assert.equal(recoveries,1);
});

test('exhausted recovery identifies the platform and retains the duplicate guard', async () => {
  const state=store();let recoveries=0;
  state.setItem(`clipforge:upload-request:youtube:job:${input.clipUrl}`,JSON.stringify({baseline:{}}));
  const submit=createQueueSubmitter(async url=>{
    if(url.endsWith('/reconcile')){recoveries++;throw new TypeError('Offline');}
    return json([]);
  },()=>state,message);
  await assert.rejects(submit(input),/YouTube.*3 percobaan/);
  assert.equal(recoveries,3);assert.equal(state.data.size,1);
});

test('loopback alternatives are explicit aliases and retain the configured path and port', () => {
  assert.deepEqual(uploadApiBases('http://localhost:8010'),['http://localhost:8010','http://127.0.0.1:8010','']);
  assert.deepEqual(uploadApiBases('http://127.0.0.1:8010/'),['http://127.0.0.1:8010','http://localhost:8010','']);
  assert.deepEqual(uploadApiBases('https://api.example.test'),['https://api.example.test','']);
  assert.deepEqual(uploadApiBases(''),['']);
});

test('a broken primary read selects a healthy backend before the one ordinary submission', async () => {
  const posts=[];
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(url.startsWith('http://api.test'))throw new TypeError('Connection refused');
    if(options.method==='POST'){posts.push(url);return json(row());}
    return json([]);
  },()=>store(),message);
  assert.equal((await submit({...input,fallbackBaseUrls:['http://127.0.0.1:8010']})).id,'accepted');
  assert.deepEqual(posts,['http://127.0.0.1:8010/api/jobs/job/youtube-uploads']);
});

test('a failed primary recovery changes address without replaying the normal POST', async () => {
  const posts=[];const state=store();
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(options.method==='POST'){
      posts.push(url);
      if(url==='http://127.0.0.1:8010/api/jobs/job/youtube-uploads/reconcile')return json(row());
      throw new TypeError('Connection reset');
    }
    return json([]);
  },()=>state,message);
  assert.equal((await submit({...input,fallbackBaseUrls:['http://127.0.0.1:8010']})).id,'accepted');
  assert.deepEqual(posts,[
    'http://api.test/api/jobs/job/youtube-uploads',
    'http://api.test/api/jobs/job/youtube-uploads/reconcile',
    'http://127.0.0.1:8010/api/jobs/job/youtube-uploads/reconcile',
  ]);
  assert.equal(state.data.size,0);
});

test('a 502 proxy falls back to serialized direct admission even when proxy GET works', async () => {
  const state=store();const posts=[];
  state.setItem(`clipforge:upload-request:youtube:job:${input.clipUrl}`,JSON.stringify({baseline:{}}));
  const submit=createQueueSubmitter(async (url,options={})=>{
    if(options.method==='POST'){
      posts.push(url);
      return url.startsWith('http://127.0.0.1:8010')?json(row()):json({detail:'Backend API is not reachable'},502);
    }
    return json([]);
  },()=>state,message);
  assert.equal((await submit({...input,baseUrl:'',fallbackBaseUrls:['http://127.0.0.1:8010']})).id,'accepted');
  assert.deepEqual(posts,['/api/jobs/job/youtube-uploads/reconcile','http://127.0.0.1:8010/api/jobs/job/youtube-uploads/reconcile']);
});

test('an existing confirmed upload clears a stale reservation without another POST', async () => {
  const state=store();let posts=0;
  state.setItem(`clipforge:upload-request:youtube:job:${input.clipUrl}`,JSON.stringify({baseline:{}}));
  const submit=createQueueSubmitter(async (_url,options={})=>{
    if(options.method==='POST')posts++;
    return json([row({status:'completed',upload_confirmed:true})]);
  },()=>state,message);
  assert.equal((await submit(input)).status,'completed');assert.equal(posts,0);assert.equal(state.data.size,0);
});
