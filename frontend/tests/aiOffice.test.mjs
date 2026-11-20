import assert from 'node:assert/strict';
import test from 'node:test';
import { officeStatus, officeTime } from '../lib/aiOffice.ts';

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
