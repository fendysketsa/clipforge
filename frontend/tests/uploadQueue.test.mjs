import assert from 'node:assert/strict';
import test from 'node:test';
import { uploadQueuePosition } from '../lib/uploadQueue.ts';

test('waiting ranks include the active upload and remain platform-specific', () => {
  const uploads = [
    { id:'active', status:'running' },
    ...[1,2,3].map(rank=>({ id:`q${rank}`, status:'queued', queue_position:rank, queue_total:3 })),
  ];
  assert.deepEqual(uploadQueuePosition(uploads[2],uploads), {position:3,total:4,ahead:2,hint:'2 video di depan'});
  assert.deepEqual(uploadQueuePosition(uploads[0],uploads), {position:1,total:4,ahead:0,hint:'3 video menunggu setelah ini'});
  const other = [{id:'tt',status:'queued',queue_position:1,queue_total:1}];
  assert.deepEqual(uploadQueuePosition(other[0],other), {position:1,total:1,ahead:0,hint:'Giliran berikutnya'});
});

test('completed records and missing positions never display an invented rank', () => {
  assert.equal(uploadQueuePosition({id:'done',status:'completed',queue_position:3,queue_total:5},[]),null);
  assert.equal(uploadQueuePosition({id:'old',status:'queued'},[]),null);
  assert.equal(uploadQueuePosition({id:'invalid',status:'queued',queue_position:0},[]),null);
});

test('queue progress updates from each backend snapshot', () => {
  const waiting = {id:'waiting',status:'queued',queue_position:2,queue_total:2};
  assert.equal(uploadQueuePosition(waiting,[{id:'active',status:'running'},waiting]).position,3);
  waiting.queue_position=1;waiting.queue_total=1;
  assert.equal(uploadQueuePosition(waiting,[waiting]).position,1);
  assert.equal(uploadQueuePosition(waiting,[waiting]).total,1);
});
