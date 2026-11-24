import assert from 'node:assert/strict';
import test from 'node:test';
import { officeIncidents, officeMotion, officeStatus, officeTime } from '../lib/aiOffice.ts';

const now = Date.parse('2026-11-21T01:00:00Z');
const snapshot = overrides => ({version:1, enabled:true, worker_running:true, state:'working',
  label:'Koordinator sedang bekerja', detail:'Memeriksa hasil worker.', last_tick_at:'2026-11-21T00:59:50Z',
  next_tick_at:'2026-11-21T01:00:20Z', departments:[], tasks:[], ...overrides});

test('old or unavailable observations cannot present an active coordinator as currently working', () => {
  for (const [value, failed] of [[snapshot({last_tick_at:'2026-11-21T00:50:00Z'}),false],
    [snapshot({last_tick_at:'invalid'}),false], [snapshot({worker_running:false}),false], [snapshot({}),true]]) {
    const result = officeStatus(value,now,failed);
    assert.equal(result.state,'degraded');
    assert.equal(result.stale,true);
  }
  assert.equal(officeStatus(snapshot({}),now).state,'working');
});

test('an operator pause stays disabled through stale data or read failures', () => {
  const paused = snapshot({enabled:false, state:'disabled', label:'Dijeda operator', last_tick_at:'invalid'});
  const result = officeStatus(paused,now,true);
  assert.equal(result.state,'disabled');
  assert.equal(result.label,'Dijeda operator');
});

test('startup and an unavailable endpoint describe uncertainty without invented work', () => {
  assert.equal(officeStatus(null,now,false).state,'starting');
  assert.match(officeStatus(null,now,true).label,/belum tersedia/);
  assert.equal(officeStatus(snapshot({state:'starting',last_tick_at:null}),now).state,'starting');
});

test('office times consistently use the operating timezone and handle missing data', () => {
  assert.match(officeTime('2026-11-21T01:00:00Z'),/08\.00 WIB/);
  assert.equal(officeTime(null),'Belum tersedia');
  assert.equal(officeTime('bad'),'Belum tersedia');
});

test('worker motion requires actual working state and a positive activity count', () => {
  const value=snapshot({departments:[
    {id:'production',state:'working',active_count:1},
    {id:'quality',state:'waiting',active_count:2},
    {id:'cleanup',state:'working',active_count:0},
    {id:'facebook',state:'working',active_count:NaN},
  ]});
  const motion=officeMotion(value,now);
  assert.equal(motion.canAnimate,true);
  assert.deepEqual(motion.activeDepartments,['production']);
});

test('stale, unavailable, paused or missing managers never authorize process motion', () => {
  for(const value of [null,snapshot({enabled:false}),snapshot({worker_running:false}),
    snapshot({last_tick_at:'2026-11-21T00:50:00Z'}),snapshot({state:'starting',last_tick_at:null})]) {
    const motion=officeMotion(value,now);
    assert.equal(motion.canAnimate,false);
    assert.equal(motion.monitoring,false);
  }
  assert.equal(officeMotion(snapshot({}),now,true).canAnimate,false);
});

test('healthy idle monitoring has a heartbeat without inventing worker progress', () => {
  const motion=officeMotion(snapshot({state:'waiting'}),now);
  assert.equal(motion.monitoring,true);
  assert.deepEqual(motion.activeDepartments,[]);
});

test('a hidden or manually paused view stops motion while retaining observed worker state', () => {
  const value=snapshot({departments:[{id:'production',state:'working',active_count:1}]});
  const motion=officeMotion(value,now,false,false);
  assert.equal(motion.canAnimate,false);
  assert.equal(motion.monitoring,false);
  assert.deepEqual(motion.activeDepartments,['production']);
});

test('incident views keep automatic, operator and department ownership distinct',()=>{
  const value=snapshot({incidents:[
    {id:'a',department:'recovery',state:'waiting',automatic:true},
    {id:'b',department:'quality',state:'needs_operator',automatic:false},
    {id:'c',department:'recovery',state:'resolved',automatic:true},
  ]});
  assert.deepEqual(officeIncidents(value).map(row=>row.id),['a','b']);
  assert.deepEqual(officeIncidents(value,'automatic').map(row=>row.id),['a']);
  assert.deepEqual(officeIncidents(value,'operator').map(row=>row.id),['b']);
  assert.deepEqual(officeIncidents(value,'all','quality').map(row=>row.id),['b']);
  assert.deepEqual(officeIncidents(null),[]);
});
