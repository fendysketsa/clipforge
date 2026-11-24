import assert from 'node:assert/strict';
import test from 'node:test';
import { OFFICE_PEOPLE, officeDestination, officePath, officeStep } from '../lib/officeChoreography.ts';

const DOORS = [-11.2, -6, 0, 7.8];
const STATES = ['running', 'queued', 'blocked', 'idle', 'running'];

function walk(index, state) {
  let point = { ...OFFICE_PEOPLE[index].desk };
  const target = officeDestination(index, state);
  let path = officePath(point, target), steps = 0;
  while (path.length && steps++ < 3000) {
    const previous = { ...point };
    const next = officeStep(point, path, .05);
    point = { x: next.x, z: next.z, y: next.y };
    path = next.path;
    const level = point.y ?? 0;
    if (level < .5) {
      if ((previous.z + 1.4) * (point.z + 1.4) < 0) {
        assert.ok(DOORS.some(door => Math.abs(point.x - door) < .95),
          `${OFFICE_PEOPLE[index].id}/${state}: tembus kaca depan di x=${point.x}`);
      }
      for (const wall of [-4.25, 4.25]) {
        if ((previous.x - wall) * (point.x - wall) < 0 && point.z < -1.6 && Math.abs(point.z + 2.4) > 1) {
          assert.fail(`${OFFICE_PEOPLE[index].id}/${state}: tembus partisi lantai 1 x=${wall}`);
        }
      }
    } else {
      for (const wall of [-4.3, 4.3]) {
        if ((previous.x - wall) * (point.x - wall) < 0 && point.z < -1.6 && Math.abs(point.z + 4.6) > .85) {
          assert.fail(`${OFFICE_PEOPLE[index].id}/${state}: tembus partisi lantai 2 x=${wall}`);
        }
      }
    }
    assert.ok(point.x > -13.6 && point.x < 12.4 && point.z > -7.5 && point.z < 7,
      `${OFFICE_PEOPLE[index].id}/${state}: keluar area`);
  }
  assert.equal(path.length, 0, `${OFFICE_PEOPLE[index].id}/${state}: rute tidak selesai`);
  assert.ok(Math.hypot(point.x - target.x, point.z - target.z,
    (point.y ?? 0) - (target.y ?? 0)) < .01, `${OFFICE_PEOPLE[index].id}/${state}: tidak sampai tujuan`);
}

test('setiap agen mencapai tujuan tanpa menembus dinding atau partisi', () => {
  for (let i = 0; i < OFFICE_PEOPLE.length; i++) for (const state of STATES) walk(i, state);
});

test('tidak ada agen yang selalu dikirim ke toilet', () => {
  const venues = new Map();
  for (let i = 0; i < OFFICE_PEOPLE.length; i++) {
    for (const state of ['queued', 'blocked', 'idle']) venues.set(OFFICE_PEOPLE[i].id,
      [...(venues.get(OFFICE_PEOPLE[i].id) || []), officeDestination(i, state).activity]);
  }
  for (const [id, list] of venues) {
    if (list.filter(row => row === 'toilet').length >= 2) {
      assert.fail(`${id} terlalu sering ke toilet: ${list.join(',')}`);
    }
  }
});
