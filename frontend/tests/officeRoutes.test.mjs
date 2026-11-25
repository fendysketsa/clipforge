import assert from 'node:assert/strict';
import test from 'node:test';
import { DIRECTOR_PATROL_SECONDS, DIRECTOR_ROUTE, OFFICE_PEOPLE, PERSONAL_RADIUS, directorState, officeAvoidStep, officeBlocked, officeDestination, officeMotionFromWork, officePath, officeStep, patrolIndex } from '../lib/officeChoreography.ts';

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

test('pimpinan keliling ke setiap karyawan lalu kembali ke meja dan ruang rapat', () => {
  const director = OFFICE_PEOPLE.findIndex(row => row.id === 'director');
  assert.equal(directorState(0), 'observing');
  const visited = new Set();
  for (let second = 24; second < 24 + DIRECTOR_ROUTE.length * DIRECTOR_PATROL_SECONDS; second += 2) {
    const state = directorState(second);
    const index = patrolIndex(state);
    assert.ok(index >= 0, `menit ${second}: tidak sedang keliling`);
    visited.add(index);
    const target = officeDestination(director, state);
    assert.equal(target.activity, 'patrol');
    const desk = OFFICE_PEOPLE[index].desk;
    assert.ok(Math.hypot(target.x - desk.x, target.z - desk.z) < 1.3, 'tidak berhenti di dekat meja karyawan');
    assert.ok(target.x > -12.3 && target.x < 12.3 && target.z > -6.5 && target.z < -1.4,
      'titik keliling di luar ruangan');
  }
  assert.equal(visited.size, DIRECTOR_ROUTE.length, 'tidak semua karyawan dikunjungi');
  assert.equal(directorState(24 + DIRECTOR_ROUTE.length * DIRECTOR_PATROL_SECONDS + 1), 'briefing');
  assert.equal(patrolIndex('observing'), -1);
});

test('gerakan karyawan mengikuti state dan tahap worker nyata', () => {
  const fallback = 'desk';
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Mentranskripsi' }, fallback), 'reading');
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Memeriksa kualitas' }, fallback), 'notice');
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Mengirim ke YouTube' }, fallback), 'chat');
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Mencari sumber' }, fallback), 'notice');
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Memperbaiki hasil' }, fallback), 'write');
  assert.equal(officeMotionFromWork({ state: 'queued', stage: 'Menunggu giliran' }, fallback), 'queued');
  assert.equal(officeMotionFromWork({ state: 'blocked', stage: 'Menunggu review' }, fallback), 'blocked');
  assert.equal(officeMotionFromWork({ state: 'idle', stage: '' }, fallback), 'idle');
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Memeriksa kualitas', stage_key: 'download' }, fallback), 'desk', 'stage_key menang dari label');
  assert.equal(officeMotionFromWork({ state: 'running', stage: 'Memeriksa kualitas', stage_key: 'youtube_upload' }, fallback), 'chat');
  assert.equal(officeMotionFromWork({ state: 'unavailable', stage: '' }, fallback), 'unavailable');
  assert.equal(officeMotionFromWork({ state: 'paused', stage: '' }, 'sofa'), 'sofa');
  assert.equal(officeMotionFromWork(undefined, 'desk'), 'desk');
  for (const state of ['reading', 'notice', 'chat', 'write', 'queued', 'blocked', 'idle']) {
    assert.ok(officeDestination(1, state).activity, `tahap ${state} tidak punya pose kerja`);
  }
});

test('kendala nyata mengalihkan pimpinan ke departemen terkait', () => {
  assert.equal(directorState(0, 3), 'patrol:3');
  assert.equal(patrolIndex(directorState(120, 5)), 5);
  assert.equal(directorState(0, -1), 'observing');
  assert.equal(directorState(0, 6), 'observing', 'pimpinan tidak mengawasi dirinya sendiri');
  const target = officeDestination(6, directorState(0, 3));
  assert.equal(target.activity, 'patrol');
  assert.ok(Math.hypot(target.x - OFFICE_PEOPLE[3].desk.x, target.z - OFFICE_PEOPLE[3].desk.z) < 1.3);
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
