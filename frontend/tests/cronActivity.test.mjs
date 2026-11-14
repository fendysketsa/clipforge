import assert from 'node:assert/strict';
import test from 'node:test';
import { cronActivityView, cronDate, cronLongActivity } from '../lib/cronActivity.ts';

const now = Date.parse('2026-11-14T01:00:00Z');
const snapshot = () => ({enabled: true, scheduler_running: true, message: 'Antrean penuh',
  activity: {state: 'capacity_wait', label: 'Menunggu kapasitas', detail: '11/11 penuh', progress_percent: null},
  scheduler_health: {last_tick_at: new Date(now).toISOString()}});

test('full capacity is waiting without fabricated progress', () => {
  const view = cronActivityView(snapshot(), now, now, false);
  assert.equal(view.label, 'Menunggu kapasitas');
  assert.equal(view.nextLabel, 'Cek kapasitas berikutnya');
  assert.equal(view.busy, false);
  assert.equal(view.percent, null);
});
test('network failure preserves the last activity with an explicit warning', () => {
  const view = cronActivityView(snapshot(), now, now, true);
  assert.equal(view.label, 'Menunggu kapasitas');
  assert.match(view.issue, /data terakhir/);
  assert.equal(view.tone, 'warning');
});
test('stale data and a stale scheduler heartbeat are independently visible', () => {
  assert.match(cronActivityView(snapshot(), now-60_000, now, false).issue, /data terakhir/);
  const state = snapshot();
  state.scheduler_health.last_tick_at = new Date(now-180_000).toISOString();
  assert.match(cronActivityView(state, now, now, false).issue, /2 menit/);
  state.enabled = false;
  assert.equal(cronActivityView(state, now, now, false).issue, null);
});
test('live progress stays visible when future cron launches are off', () => {
  const state = snapshot(); state.enabled = false;
  state.activity = {state:'running', label:'Cron sedang bekerja', detail:'Merender', progress_percent:62};
  const view = cronActivityView(state, now, now, false);
  assert.equal(view.busy, true); assert.equal(view.percent, 62);
});
test('loading and an older API never claim to be rendering', () => {
  assert.equal(cronActivityView(null, null, now, false).state, 'loading');
  const state = snapshot(); delete state.activity;
  assert.equal(cronActivityView(state, now, now, false).busy, false);
  state.scheduler_running = false;
  assert.equal(cronActivityView(state, now, now, false).tone, 'warning');
});
test('timestamps consistently use WIB and tolerate missing values', () => {
  assert.match(cronDate('2026-11-14T01:00:00Z'), /08\.00\.00 WIB/);
  assert.equal(cronDate('invalid'), 'Belum tersedia');
});

test('an empty Long lane explains its actual wait instead of claiming a render is active', () => {
  assert.match(cronLongActivity('waiting_for_eligible_short', true), /Menunggu sumber/);
  assert.match(cronLongActivity('waiting_for_qc', true), /hasil QC/);
  assert.match(cronLongActivity('reserved', true), /pemeriksaan/);
  assert.match(cronLongActivity('queued', false), /dinonaktifkan/);
  assert.doesNotMatch(cronLongActivity(undefined, true), /sedang dirender|selesai/);
});
