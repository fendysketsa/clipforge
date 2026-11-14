import assert from 'node:assert/strict';
import test from 'node:test';
import { studioQueueItems, queueDate } from '../lib/studioQueue.ts';
import { studioViewFromHash } from '../lib/workspaceNavigation.ts';

const upload = (changes = {}) => ({id:'one', title:'Contoh video', clip_name:'clip.mp4',
  status:'completed', updated_at:'2026-11-14T01:00:00Z', dry_run:false,
  visibility:'private', upload_confirmed:true, video_url:'https://www.youtube.com/watch?v=AbCdEfGh123', ...changes});

test('completed jobs require confirmation and an exact video ID before appearing verified', () => {
  assert.equal(studioQueueItems([upload()],[])[0].state,'verified');
  assert.equal(studioQueueItems([upload({upload_confirmed:false})],[])[0].state,'attention');
  assert.equal(studioQueueItems([upload({video_url:'https://studio.youtube.com'})],[])[0].state,'attention');
  assert.equal(studioQueueItems([upload({video_url:null,file_selection_started:true})],[])[0].state,'attention');
});
test('real queues preserve active states and collapse repeated records of the same YouTube video', () => {
  const rows=studioQueueItems([upload(),upload({id:'new',updated_at:'2026-11-14T02:00:00Z'}),
    upload({id:'queued',video_url:null,status:'queued'})],[]);
  assert.equal(rows.length,2);
  assert.equal(rows.find(row=>row.state==='verified').id,'youtube-new');
  assert.equal(rows.find(row=>row.id==='youtube-queued').state,'queued');
  assert.equal(studioQueueItems([upload({dry_run:true})],[]).length,0);
});
test('cancelled submissions remain visible when the remote result is uncertain', () => {
  assert.equal(studioQueueItems([upload({status:'cancelled',upload_confirmed:false})],[])[0].state,'attention');
  const base={id:'tt',caption:'Post',clip_name:'clip',updated_at:'2026-11-14T01:00:00Z',status:'cancelled',logs:[]};
  assert.equal(studioQueueItems([],[base]).length,0);
  assert.equal(studioQueueItems([],[{...base,submission_accepted:true}])[0].state,'attention');
  assert.equal(studioQueueItems([],[{...base,logs:['POST_SUBMIT_INTENT: prior attempt']}])[0].state,'attention');
});
test('scheduled and private labels remain distinct and dates consistently use WIB', () => {
  assert.equal(studioQueueItems([upload()],[])[0].privacy,'Private');
  assert.equal(studioQueueItems([upload({publish_at:'2099-01-01T01:00:00Z'})],[])[0].privacy,'Terjadwal');
  assert.match(queueDate('2026-11-14T01:00:00Z'),/08\.00 WIB/);
  assert.equal(queueDate('invalid'),'Waktu belum tersedia');
});
test('TikTok needs an exact post URL, not merely the account profile', () => {
  const row={id:'tt',status:'completed',upload_confirmed:true,profile_url:'https://www.tiktok.com/@channel',updated_at:'2026-11-14T01:00:00Z'};
  assert.equal(studioQueueItems([],[row])[0].state,'attention');
  assert.equal(studioQueueItems([],[{...row,profile_url:'https://www.tiktok.com/@channel/video/1234567890123456789'}])[0].state,'verified');
});
test('deep links select the requested workspace and unknown hashes safely select creation', () => {
  for(const key of ['results','history','automation','settings']) assert.equal(studioViewFromHash('#'+key),key);
  assert.equal(studioViewFromHash('#quick-start-title'),'create');
  assert.equal(studioViewFromHash('#unknown'),'create');
});
