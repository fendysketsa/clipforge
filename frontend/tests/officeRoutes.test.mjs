import assert from 'node:assert/strict';
import test from 'node:test';
import { OFFICE_PEOPLE, PERSONAL_RADIUS, officeAvoidStep, officeBlocked, officeDestination, officePath, officeStep } from '../lib/officeChoreography.ts';

const DOORS = [-11.2, 0, 7.8];
const PARTITION_GAP = [-3.25, -1.55];
const STATES = ['running', 'queued', 'blocked', 'idle', 'notice', 'briefing', 'running'];

test('setiap agen mencapai tujuan tanpa menembus kaca atau partisi', () => {
  for (let i = 0; i < OFFICE_PEOPLE.length; i++) {
    let point = { ...OFFICE_PEOPLE[i].desk };
    for (const state of STATES) {
      const target = officeDestination(i, state);
      let path = officePath(point, target), steps = 0;
      assert.ok(target.x > -12.3 && target.x < 12.3 && target.z > -7 && target.z < 7,
        `${OFFICE_PEOPLE[i].id}/${state}: tujuan di luar area`);
      while (path.length && steps++ < 3000) {
        const previous = { ...point };
        const next = officeStep(point, path, .05);
        point = { x: next.x, z: next.z };
        path = next.path;
        if ((previous.z + 1.4) * (point.z + 1.4) < 0) {
          assert.ok(DOORS.some(door => Math.abs(point.x - door) < .95),
            `${OFFICE_PEOPLE[i].id}/${state}: tembus kaca depan di x=${point.x.toFixed(2)}`);
        }
        for (const wall of [-4.25, 4.25]) {
          if ((previous.x - wall) * (point.x - wall) < 0 && point.z < -1.4) {
            assert.ok(point.z >= PARTITION_GAP[0] && point.z <= PARTITION_GAP[1],
              `${OFFICE_PEOPLE[i].id}/${state}: tembus partisi x=${wall} z=${point.z.toFixed(2)}`);
          }
        }
        assert.ok(Math.hypot(point.x - previous.x, point.z - previous.z) <= .1,
          `${OFFICE_PEOPLE[i].id}/${state}: gerakan melompat`);
        const inTable = (x, z) => x > -10.5 && x < -5.5 && z > .5 && z < 3.5;
        assert.ok(!(inTable(previous.x, previous.z) && inTable(point.x, point.z)),
          `${OFFICE_PEOPLE[i].id}/${state}: menabrak meja rapat`);
      }
      assert.equal(path.length, 0, `${OFFICE_PEOPLE[i].id}/${state}: rute tidak selesai`);
      assert.ok(Math.hypot(point.x - target.x, point.z - target.z) < .01,
        `${OFFICE_PEOPLE[i].id}/${state}: tidak sampai tujuan`);
    }
  }
});

test('pejalan menghindar atau berhenti saat ada orang di depan, tidak menembus', () => {
  const from = { x: -1, z: 4.4 };
  const desired = { x: -.6, z: 4.4 };
  const others = [{ x: -.2, z: 4.4 }];
  const result = officeAvoidStep(from, desired, [], others);
  assert.equal(result.greeting, true);
  assert.equal(result.blocker, 0);
  assert.ok(!officeBlocked(result.point, others), 'titik akhir masih menimpa rekan');
  assert.ok(result.point.x >= -11.9 && result.point.x <= 11.9 && result.point.z >= -1.35 && result.point.z <= 6.4,
    'menghindar keluar area aman');
  const detour = result.path[0];
  assert.ok(detour && Math.abs(detour.z - 4.4) > .3, 'tidak ada titik menyamping');
  assert.ok(!officeBlocked(detour, others), 'titik menyamping menimpa rekan');
  assert.ok(result.path.length >= 2, 'tujuan aslinya masih disimpan');
});

test('pejalan berhenti menyapa bila kedua sisi juga penuh', () => {
  const from = { x: 0, z: 4.4 };
  const desired = { x: .2, z: 4.4 };
  const others = [{ x: .6, z: 4.4 }, { x: -.6, z: 4.4 }, { x: 0, z: 5.02 }, { x: 0, z: 3.78 }];
  const result = officeAvoidStep(from, desired, [], others);
  assert.equal(result.greeting, true);
  assert.deepEqual(result.point, from);
});

test('langkah bebas tetap lewat tanpa memicu sapaan', () => {
  const from = { x: 0, z: 4.4 };
  const desired = { x: .2, z: 4.4 };
  const others = [{ x: 6, z: -4 }];
  const result = officeAvoidStep(from, desired, [], others);
  assert.equal(result.greeting, false);
  assert.equal(result.blocker, -1);
  assert.deepEqual(result.point, desired);
  assert.ok(PERSONAL_RADIUS > 0);
});

test('pimpinan punya ruang sendiri dan turun ke ruang rapat saat memberi arahan', () => {
  const director = OFFICE_PEOPLE.findIndex(row => row.id === 'director');
  assert.ok(director >= 0);
  const desk = officeDestination(director, 'observing');
  const brief = officeDestination(director, 'briefing');
  assert.equal(desk.activity, 'observing');
  assert.equal(brief.activity, 'briefing');
  assert.ok(Math.hypot(desk.x - brief.x, desk.z - brief.z) > 3, 'Pimpinan tidak benar-benar berpindah');
});
