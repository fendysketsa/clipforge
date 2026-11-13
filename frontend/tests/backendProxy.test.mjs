import assert from 'node:assert/strict';
import test from 'node:test';
import { createBackendProxy } from '../lib/backendProxy.ts';

const incoming = (method='GET',body) => new Request('http://localhost:3000/api/jobs/job/youtube-uploads?check=1', {
  method,...(body===undefined?{}:{body}),headers:{'content-type':'application/json'},
});
const outage = () => { throw new TypeError('Container bridge unavailable'); };

test('failed discovery redirects browser before reading or forwarding a POST', async () => {
  const methods=[];
  const proxy=createBackendProxy({backendBases:['http://172.18.0.1:8010'],browserApiBase:'http://localhost:8010',
    fetcher:async (url,options={})=>{methods.push(options.method||'GET');return outage();}});
  const request=incoming('POST','{"clip_url":"/outputs/test.mp4"}');
  const result=await proxy(request,'/api/jobs/job/youtube-uploads');
  assert.equal(result.status,307);
  assert.equal(result.headers.get('location'),'http://localhost:8010/api/jobs/job/youtube-uploads?check=1');
  assert.equal(result.headers.get('x-clipforge-transport'),'browser-direct-before-forward');
  assert.equal(result.headers.get('cache-control'),'no-store');
  assert.equal(request.bodyUsed,false);assert.deepEqual(methods,['GET']);
});

test('accepted POST whose response is lost is never redirected or replayed', async () => {
  const mutations=[];
  const proxy=createBackendProxy({backendBases:['http://backend'],browserApiBase:'http://localhost:8010',
    fetcher:async (url,options={})=>{
      if(new URL(url).pathname==='/api/health')return Response.json({status:'ok'});
      mutations.push({url:String(url),body:new TextDecoder().decode(options.body)});
      return outage();
    }});
  const result=await proxy(incoming('POST','{"clip_url":"clip.mp4"}'),'/api/jobs/job/youtube-uploads');
  assert.equal(result.status,502);assert.equal(result.headers.get('location'),null);
  assert.equal(result.headers.get('x-clipforge-submission'),'unknown');
  assert.equal(mutations.length,1);assert.equal(mutations[0].body,'{"clip_url":"clip.mp4"}');
});

test('normal proxy preserves raw bytes and backend rejection', async () => {
  const bytes=new Uint8Array([0,255,128,13,10,5]);let forwarded;
  const proxy=createBackendProxy({backendBases:['http://backend'],browserApiBase:'http://localhost:8010',
    fetcher:async (url,options={})=>{
      if(new URL(url).pathname==='/api/health')return Response.json({status:'ok'});
      forwarded=new Uint8Array(options.body);return Response.json({detail:'QC ditahan'}, {status:409});
    }});
  const result=await proxy(incoming('POST',bytes),'/api/uploads');
  assert.deepEqual(forwarded,bytes);assert.equal(result.status,409);
  assert.deepEqual(await result.json(),{detail:'QC ditahan'});
});

test('invalid or same-origin public targets cannot form redirect loops or expose credentials', async () => {
  for(const browserApiBase of ['', 'http://localhost:3000','http://name:secret@localhost:8010','javascript:alert(1)']){
    const proxy=createBackendProxy({backendBases:['http://backend'],browserApiBase,fetcher:async()=>outage()});
    const result=await proxy(incoming(),'/api/health');
    assert.equal(result.status,502);assert.equal(result.headers.get('location'),null);
    assert.equal(result.headers.get('x-clipforge-submission'),'not-forwarded');
  }
});

test('healthy discovery is reused while each mutation is forwarded exactly once', async () => {
  let probes=0,mutations=0;
  const proxy=createBackendProxy({backendBases:['http://backend'],browserApiBase:'http://localhost:8010',
    fetcher:async(url)=>{
      if(new URL(url).pathname==='/api/health'){probes++;return Response.json({status:'ok'});}
      mutations++;return Response.json({id:'existing'});
    }});
  await proxy(incoming('POST','{}'),'/api/jobs/job/youtube-uploads');
  await proxy(incoming('POST','{}'),'/api/jobs/job/youtube-uploads/reconcile');
  assert.equal(probes,1);assert.equal(mutations,2);
});
