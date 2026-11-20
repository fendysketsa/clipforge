import assert from 'node:assert/strict';
import test from 'node:test';
import { studioViewFromHash } from '../lib/workspaceNavigation.ts';

test('the dashboard opens by default and existing composer deep links keep working', () => {
  assert.equal(studioViewFromHash(''), 'overview');
  assert.equal(studioViewFromHash('#overview'), 'overview');
  assert.equal(studioViewFromHash('#quick-start-title'), 'create');
  assert.equal(studioViewFromHash('#unknown-old-link'), 'create');
});

test('platform and operational deep links resolve to their original workspace', () => {
  for (const view of ['results','history','automation','facebook','settings']) {
    assert.equal(studioViewFromHash(`#${view}`), view);
  }
});
