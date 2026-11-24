import assert from 'node:assert/strict';
import test from 'node:test';
import { OFFICE_PEOPLE, officeDestination, officePath, officeStep } from '../lib/officeChoreography.ts';
import { officeAgentWork, officeActivityStatus, officeSpeech } from '../lib/aiOffice.ts';

const now=Date.parse('2026-11-24T01:00:00Z');
const snapshot=(state='running')=>({enabled:true,worker_running:true,state:'working',last_tick_at:'2026-11-24T01:00:00Z',
 activity:{version:1,available:true,observed_at:'2026-11-24T01:00:00Z',departments:[{id:'production',available:true,state,
 running_count:state==='running'?1:0,queued_count:state==='queued'?1:0,blocked_count:0,total_count:1,detail:'Status nyata',
 work:[{id:'job:one',job_id:'one',state,title:'Video nyata',stage:'Merender video',progress_percent:state==='running'?37:null}]}]}});

test('state changes use doorways and end at the destination without a repeating loop',()=>{
 for(let index=0;index<OFFICE_PEOPLE.length;index++){
  let point={...OFFICE_PEOPLE[index].desk};
  for(const state of ['idle','running','blocked','queued','idle']){
   const target=officeDestination(index,state);let path=officePath(point,target);
   for(let step=0;path.length&&step<1200;step++){
    const previous=point;const next=officeStep(point,path,.04);point={x:next.x,z:next.z,y:next.y};path=next.path;
    assert.ok(Math.hypot(point.x-previous.x,point.z-previous.z)<=.067);
    if((previous.z+1.4)*(point.z+1.4)<0)assert.ok([-12.9,-6,0,6].some(door=>Math.abs(point.x-door)<.85));
    for(const wall of [-3,3])assert.ok(!((previous.x-wall)*(point.x-wall)<0&&point.z< -1.7));
   }
   assert.equal(path.length,0);assert.ok(Math.hypot(point.x-target.x,point.z-target.z)<.001);
   const later=officeStep(point,path,600);assert.equal(later.x,point.x);assert.equal(later.z,point.z);assert.equal(later.moving,false);
  }
 }
});

test('speech uses actual job identity, stage and progress rather than generated chatter',()=>{
 assert.equal(officeSpeech(snapshot(),'production',now).text,'Merender video · 37%: Video nyata');
 assert.equal(officeAgentWork(snapshot('queued'),'production',now).running_count,0);
 assert.equal(officeSpeech(snapshot('queued'),'production',now).text,'Merender video: Video nyata');
});

test('unknown, stale, future or failed observations cannot animate made-up work',()=>{
 for(const value of [null,{...snapshot(),activity:undefined}, {...snapshot(),activity:{...snapshot().activity,available:false}},
 {...snapshot(),activity:{...snapshot().activity,observed_at:'2026-11-24T00:58:00Z'}},
 {...snapshot(),activity:{...snapshot().activity,observed_at:'2026-11-24T01:02:00Z'}}]){
  assert.equal(officeActivityStatus(value,now).fresh,false);
  const work=officeAgentWork(value,'production',now);assert.equal(work.state,'unavailable');assert.deepEqual(work.work,[]);
 }
 assert.equal(officeActivityStatus(snapshot(),now,true).fresh,false);
 assert.equal(officeAgentWork(snapshot(),'facebook',now).state,'unavailable');
});

test('coordinator pause does not conceal a manual job still running in the real queue',()=>{
 const value={...snapshot(),enabled:false,worker_running:false};
 assert.equal(officeActivityStatus(value,now).fresh,true);
 assert.equal(officeAgentWork(value,'production',now).state,'running');
});
