import assert from 'node:assert/strict';
import test from 'node:test';
import { OFFICE_PEOPLE, officeDestination, officePath, officeStep } from '../lib/officeChoreography.ts';

const STATES = ['running', 'queued', 'blocked', 'idle', 'running'];

test('setiap agen bekerja di lantai 1, tidak melintas dinding, dan sampai tujuan', () => {
  for (let i = 0; i < OFFICE_PEOPLE.length; i++) {
    let point = { ...OFFICE_PEOPLE[i].desk };
    for (const state of STATES) {
      const target = officeDestination(i, state);
      let path = officePath(point, target), steps = 0;
      assert.ok(target.z > -1.4, `${OFFICE_PEOPLE[i].id}/${state}: tujuan di belakang kaca`);
      while (path.length && steps++ < 3000) {
        const previous = { ...point };
        const next = officeStep(point, path, .05);
        point = { x: next.x, z: next.z };
        path = next.path;
        assert.ok(point.z > -1.4,
          `${OFFICE_PEOPLE[i].id}/${state}: menembus kaca depan di z=${point.z.toFixed(2)}`);
        assert.ok(point.x > -12.3 && point.x < 12.3 && point.z < 7,
          `${OFFICE_PEOPLE[i].id}/${state}: keluar area`);
        assert.ok(Math.hypot(point.x - previous.x, point.z - previous.z) <= .09,
          `${OFFICE_PEOPLE[i].id}/${state}: gerakan melompat`);
      }
      assert.equal(path.length, 0, `${OFFICE_PEOPLE[i].id}/${state}: rute tidak selesai`);
      assert.ok(Math.hypot(point.x - target.x, point.z - target.z) < .01,
        `${OFFICE_PEOPLE[i].id}/${state}: tidak sampai tujuan`);
    }
  }
});

test('tidak ada agen yang selalu dikirim ke istirahat', () => {
  for (let i = 0; i < OFFICE_PEOPLE.length; i++) {
    const activities = ['queued', 'blocked', 'idle'].map(state => officeDestination(i, state).activity);
    assert.ok(activities.filter(row => row === 'coffee' || row === 'sofa' || row === 'snack').length < 2,
      `${OFFICE_PEOPLE[i].id}: terlalu sering istirahat`);
  }
});
