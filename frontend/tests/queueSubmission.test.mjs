import assert from 'node:assert/strict';
import test from 'node:test';
import { createQueueSubmitter } from '../lib/queueSubmission.ts';

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

test('unknown outcome survives client recreation and cannot replay a POST', async () => {
  let rows=[],posts=0;const state=store();
  const fetcher=async (_url,options={})=>{
    if(options.method==='POST'){posts++;throw new TypeError('Failed to fetch');}
    return json(rows);
  };
  await assert.rejects(createQueueSubmitter(fetcher,()=>state,message)(input),/Koneksi terputus/);
  const reloaded=createQueueSubmitter(fetcher,()=>state,message);
  await assert.rejects(reloaded(input),/sebelumnya belum pasti/);
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
  const fetcher=async (_url,options={})=>{
    if(options.method==='POST'){posts++;throw new TypeError('Failed to fetch');}
    return json([row({id:'old',status:'failed',updated_at:'old'})]);
  };
  const submit=createQueueSubmitter(fetcher,()=>state,message);
  await assert.rejects(submit(input),/Koneksi terputus/);
  await assert.rejects(submit(input),/sebelumnya belum pasti/);assert.equal(posts,1);
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
  await assert.rejects(submit(input),/Koneksi antrean upload belum tersedia/);assert.equal(posts,0);
});
