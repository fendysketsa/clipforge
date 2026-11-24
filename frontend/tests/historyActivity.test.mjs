import assert from 'node:assert/strict';
import test from 'node:test';
import { historyUploadActivity, historyJobIsActive, intakeIsFresh } from '../lib/historyActivity.ts';

test('finished renders remain in active history while either platform is delivering', () => {
  const activity = historyUploadActivity([
    { source_job_id: 'short', status: 'completed', upload_confirmed: true },
    { source_job_id: 'short', status: 'running' },
    { source_job_id: 'long', status: 'queued' },
  ]);
  assert.equal(activity.count, 2);
  assert.equal(historyJobIsActive({ id: 'short', status: 'completed' }, activity.jobIds), true);
  assert.equal(historyJobIsActive({ id: 'long', status: 'completed' }, activity.jobIds), true);
  assert.equal(activity.runningJobIds.has('short'), true);
  assert.equal(activity.runningJobIds.has('long'), false);
  assert.equal(historyJobIsActive({ id: 'render', status: 'running' }, activity.jobIds), true);
});

test('completion removes delivery activity and archived or dry runs never add it', () => {
  const activity = historyUploadActivity([
    { source_job_id: 'short', status: 'completed', upload_confirmed: true },
    { source_job_id: 'short', status: 'failed' },
    { source_job_id: 'dry', status: 'running', dry_run: true },
    { source_job_id: 'archived', status: 'queued', attention_archived_at: '2026-11-22' },
  ]);
  assert.equal(activity.count, 0);
  assert.equal(historyJobIsActive({ id: 'short', status: 'completed' }, activity.jobIds), false);
});

test('stopped operator snapshots cannot promise that upload is still preparing', () => {
  const now = 1_795_000_000_000;
  assert.equal(intakeIsFresh(now / 1000 - 30, now), true);
  for (const stamp of [undefined, NaN, Infinity, now / 1000 - 91, now / 1000 + 31]) {
    assert.equal(intakeIsFresh(stamp, now), false);
  }
});
