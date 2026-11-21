import assert from 'node:assert/strict';
import test from 'node:test';
import { automaticHandlingView, automaticUploadSummary } from '../lib/automaticHandling.ts';

const handling = (changes={}) => ({state:'waiting', action:'verify_upload',
  reason:'Bukti sedang dicocokkan oleh server.',next_check_at:'2026-11-21T01:00:00Z',urgent:false,...changes});

test('routine failures expose scheduled automatic work without requesting user action',()=>{
  const view=automaticHandlingView(handling());
  assert.equal(view.label,'Terjadwal otomatis');
  assert.equal(view.urgent,false);
  assert.equal(view.detail,'Bukti sedang dicocokkan oleh server.');
  assert.equal(view.nextCheckAt,'2026-11-21T01:00:00Z');
  assert.equal(automaticHandlingView(undefined),null);
});

test('only an explicit urgent signal requests human action',()=>{
  assert.equal(automaticHandlingView(handling({reason:'Login mungkin perlu diperiksa.'})).urgent,false);
  assert.equal(automaticHandlingView(handling({state:'urgent',urgent:false})).label,'Menunggu sistem');
  const urgent=automaticHandlingView(handling({state:'urgent',urgent:true}));
  assert.equal(urgent.label,'Perlu tindakan Anda');assert.equal(urgent.urgent,true);
});

test('archive outcomes are terminal bookkeeping and never imply a verified upload',()=>{
  const archived=automaticUploadSummary(handling({state:'archived',action:'archive_rejected'}),'idle');
  assert.equal(archived.state,'cancelled');assert.equal(archived.label,'Diarsipkan otomatis');
  assert.equal(automaticUploadSummary(handling({state:'archiving'}),'failed').label,'Dibersihkan otomatis');
});

test('actual progress and confirmed platform evidence remain authoritative',()=>{
  for(const state of ['running','queued','verified','partial']) {
    assert.equal(automaticUploadSummary(handling({state:'archiving'}),state),null);
    assert.equal(automaticUploadSummary(handling({state:'urgent',urgent:true}),state),null);
  }
  assert.equal(automaticUploadSummary(undefined,'idle'),null);
  assert.equal(automaticUploadSummary(handling({state:'processing'}),'unverified').label,'Sedang ditangani otomatis');
});
