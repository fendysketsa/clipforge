import assert from 'node:assert/strict';
import test from 'node:test';
import {createReadRequest} from '../lib/readRequest.ts';
import {createPollingTask} from '../lib/pollTask.ts';

const json=value=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});

test('overlapping status reads share a fetch but a later read is fresh', async()=>{
  let calls=0,release;
  const gate=new Promise(resolve=>{release=resolve;});
  const read=createReadRequest(async()=>{calls++;await gate;return json({count:calls});});
  const pending=Array.from({length:20},()=>read('/jobs','offline'));
  await Promise.resolve();assert.equal(calls,1);release();
  const rows=await Promise.all(pending);assert.ok(rows.every(row=>row.count===1));
  assert.equal((await read('/jobs','offline')).count,2);
});

for (const failure of ['http','sync','json']) test(`a ${failure} failure releases the read for recovery`,async()=>{
  let calls=0;
  const read=createReadRequest(()=>{
    calls++;
    if(calls===1){
      if(failure==='sync')throw new TypeError('offline');
      if(failure==='http')return Promise.resolve(new Response('{"detail":"hold"}',{status:503}));
      return Promise.resolve(new Response('{'));
    }
    return Promise.resolve(json({ok:true}));
  });
  await assert.rejects(read('/status','offline'));
  assert.equal((await read('/status','offline')).ok,true);
  assert.equal(calls,2);
});

test('different backend addresses and routes remain independent',async()=>{
  const urls=[];
  const read=createReadRequest(async(url,options)=>{
    urls.push(url);assert.ok(options.signal instanceof AbortSignal);assert.equal(options.cache,'no-store');
    return json({url});
  });
  await Promise.all(['/a','/b','http://other/a'].map(url=>read(url,'offline')));
  assert.equal(urls.length,3);
});

test('polling skips overlap and hidden pages; stopped tasks cannot apply late results',async()=>{
  let enabled=false,calls=0,applied=0,release;
  const gate=new Promise(resolve=>{release=resolve;});
  const poll=createPollingTask(async current=>{calls++;await gate;if(current())applied++;},()=>enabled);
  await poll.run();assert.equal(calls,0);enabled=true;
  const first=poll.run();await poll.run();assert.equal(calls,1);
  poll.stop();release();await first;await poll.run();
  assert.equal(calls,1);assert.equal(applied,0);
});

test('a rejected status poll does not disable future polls',async()=>{
  let calls=0;
  const poll=createPollingTask(async()=>{if(++calls===1)throw new Error('offline');});
  await poll.run();await poll.run();assert.equal(calls,2);
});
