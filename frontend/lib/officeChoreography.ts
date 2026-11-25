export type OfficePoint = { x: number; z: number; y?: number };
export type OfficeActivity = "desk" | "walk" | "greet" | "patrol" | "meeting" | "briefing" | "observing" | "notice" | "chat" | "coffee" | "lounge" | "sofa" | "reading" | "write" | "call" | "copy" | "snack" | "cards";

// One floor only. Every working spot is in the open front area (z > -1.4),
// so nobody ever has to cross the glass partition or a wall to do their job.
export const OFFICE_PEOPLE = [
  { id: "production", name: "Raka", role: "Produksi", color: "#4f9383", desk: { x: -9, z: -4 } },
  { id: "quality", name: "Naya", role: "Quality control", color: "#9880bd", desk: { x: -6.5, z: -4 } },
  { id: "distribution", name: "Dimas", role: "Distribusi", color: "#588db7", desk: { x: 6.5, z: -4 } },
  { id: "recovery", name: "Bima", role: "Pemulihan", color: "#c28d54", desk: { x: 9, z: -4 } },
  { id: "cleanup", name: "Sari", role: "Pengelola aset", color: "#7c9b5b", desk: { x: -9, z: -1.8 } },
  { id: "facebook", name: "Mika", role: "Facebook", color: "#697db8", desk: { x: -6.5, z: -1.8 } },
  { id: "director", name: "Pimpinan", role: "Direktur Studio", color: "#c99433", desk: { x: .5, z: -4 } },
] as const;

// The director does one calm round of the floor: monitor his own screen,
// visit every colleague at their desk to ask what they are doing, then brief
// the team in the meeting room. Each stop lasts long enough to be readable.
export const DIRECTOR_PATROL_SECONDS = 36;
// Finish one room before crossing to the next, instead of zigzagging between
// the left and right rooms on every stop.
export const DIRECTOR_ROUTE = [0, 1, 4, 5, 2, 3];

export function directorState(seconds: number, attention = -1): string {
  // A live blocker overrides the routine: the director goes straight to that
  // department and stays there until the repair is no longer observed.
  if (attention >= 0 && OFFICE_PEOPLE[attention] && OFFICE_PEOPLE[attention].id !== 'director') {
    return `patrol:${attention}`;
  }
  const observe = 24, briefing = 24;
  const cycle = observe + DIRECTOR_ROUTE.length * DIRECTOR_PATROL_SECONDS + briefing;
  const time = ((seconds % cycle) + cycle) % cycle;
  if (time < observe) return "observing";
  const visit = Math.floor((time - observe) / DIRECTOR_PATROL_SECONDS);
  if (visit < DIRECTOR_ROUTE.length) return `patrol:${DIRECTOR_ROUTE[visit]}`;
  return "briefing";
}

export function patrolIndex(state: string): number {
  if (!state.startsWith("patrol:")) return -1;
  const index = Number(state.slice(7));
  return Number.isInteger(index) && OFFICE_PEOPLE[index] && OFFICE_PEOPLE[index].id !== "director" ? index : -1;
}

const SPOTS: Record<'queued' | 'blocked' | 'idle', (OfficePoint & { activity: OfficeActivity })[]> = {
  queued: [
    { x: -2.6, z: 5.6, activity: "write" },
    { x: -0.6, z: 5.6, activity: "write" },
    { x: 1.4, z: 5.6, activity: "write" },
    { x: 3.4, z: 5.6, activity: "write" },
    { x: -8.8, z: 6.3, activity: "write" },
    { x: -5.5, z: 6.3, activity: "write" },
  ],
  blocked: [
    { x: -11.2, z: 1, activity: "meeting" },
    { x: -4.8, z: 1, activity: "meeting" },
    { x: -11.2, z: 2.4, activity: "meeting" },
    { x: -4.8, z: 2.4, activity: "meeting" },
    { x: -9.2, z: 4.8, activity: "call" },
    { x: -6.8, z: 4.8, activity: "call" },
  ],
  idle: [
    { x: -2.4, z: 4.8, activity: "lounge" },
    { x: 2.4, z: 4.8, activity: "coffee" },
    { x: -8.4, z: 3.6, activity: "reading" },
    { x: 10.2, z: 4.1, activity: "coffee" },
    { x: 6.6, z: 4.1, activity: "snack" },
    { x: -3, z: 2.2, activity: "cards" },
  ],
};

const TASK_BOARD_SPOTS: OfficePoint[] = [
  { x: 5.2, z: 1.2 }, { x: 5.9, z: 1.2 }, { x: 6.6, z: 1.2 },
  { x: 5.2, z: 2 }, { x: 5.9, z: 2 }, { x: 6.6, z: 2 },
];

const SOFA_SPOTS: OfficePoint[] = [{ x: -1.2, z: 5.55 }, { x: 1.5, z: 5.55 }];
const CHAT_SPOTS: OfficePoint[] = [
  { x: -2.2, z: 4.4 }, { x: -.4, z: 4.4 },
  { x: 1.4, z: 4.4 }, { x: 3.2, z: 4.4 },
  { x: 5, z: 4.4 }, { x: 6.8, z: 4.4 },
];

export type OfficeWorkCue = { state: string; stage: string; stage_key?: string; title?: string };

// The worker's own stage key is authoritative; the Indonesian label is only
// a fallback for older snapshots. This only changes where an avatar stands —
// QC, rights and publication stay with the backend owner that produced it.
const STAGE_MOTION: Record<string, string> = {
  transcribe: 'reading', transcription: 'reading', analysis: 'reading', analyze: 'reading', selection: 'reading',
  qc: 'notice', quality_control: 'notice', clip_qc: 'notice', audit: 'notice',
  preflight: 'notice', trend_discovery: 'notice', fallback_discovery: 'notice',
  quality_repair: 'write', repair: 'write',
  upload: 'chat', youtube_upload: 'chat', social_upload: 'chat', verification: 'chat',
  waiting_upload: 'queued', resume_pending_upload: 'queued', retry_upload: 'queued',
  cron_capacity_wait: 'queued', daily_upload_limit: 'queued', youtube_platform_daily_limit: 'queued',
  cleanup: 'notice', incident: 'blocked',
  source: 'desk', download: 'desk', render: 'desk', rendering: 'desk',
};

export function officeMotionFromWork(cue: OfficeWorkCue | undefined, fallback: string): string {
  if (!cue) return fallback;
  if (cue.state === 'unavailable') return 'unavailable';
  if (cue.state === 'paused') return fallback;
  if (cue.state === 'blocked') return 'blocked';
  if (cue.state === 'queued') return 'queued';
  if (cue.state === 'idle') return 'idle';
  const key = (cue.stage_key || '').toLocaleLowerCase();
  if (STAGE_MOTION[key]) return STAGE_MOTION[key];
  const stage = (cue.stage || '').toLocaleLowerCase();
  if (/qc|kualitas|audit|review|periksa|mencari sumber|penemuan/.test(stage)) return 'notice';
  if (/unggah|upload|distribusi|mengirim|kirim/.test(stage)) return 'chat';
  if (/transkrip|transcri|analisis|menganalisis|memilih klip|selection/.test(stage)) return 'reading';
  if (/perbaikan|memperbaiki|repair/.test(stage)) return 'write';
  return 'desk';
}

export function officeDestination(index: number, state: string): OfficePoint & { activity: OfficeActivity } {
  if (state === 'chat') return { ...CHAT_SPOTS[index % CHAT_SPOTS.length], activity: 'chat' };
  if (state === 'sofa') return { ...SOFA_SPOTS[index % SOFA_SPOTS.length], activity: 'sofa' };
  if (state === 'notice') return { ...TASK_BOARD_SPOTS[index % TASK_BOARD_SPOTS.length], activity: 'notice' };
  if (OFFICE_PEOPLE[index].id === 'director') {
    if (state === 'briefing') return { x: -8, z: 4.4, activity: 'briefing' };
    const visit = patrolIndex(state);
    if (visit >= 0) {
      const desk = OFFICE_PEOPLE[visit].desk;
      // Stand beside the colleague's desk, inside the same room, facing them.
      return { x: desk.x + (desk.x < 0 ? .95 : -.95), z: desk.z - .55, activity: 'patrol' };
    }
    return { ...OFFICE_PEOPLE[index].desk, activity: 'observing' };
  }
  if (state === 'queued' || state === 'blocked' || state === 'idle') return SPOTS[state][index % SPOTS[state].length];
  return { ...OFFICE_PEOPLE[index].desk, activity: 'desk' };
}

// Ground floor rooms: leave through the room's own door, walk in the open
// front corridor, then enter the destination room through its door.
export function officePath(from: OfficePoint, to: OfficePoint): OfficePoint[] {
  const doorFor = (x: number) => x < -4.25 ? -11.2 : x > 4.25 ? 7.8 : 0;
  const FRONT = 4.4, INSIDE = -2.4;
  const points: OfficePoint[] = [at(from)];
  if (from.z >= -1.4) {
    points.push(at({ x: from.x, z: FRONT }));
  } else {
    const door = doorFor(from.x);
    points.push(at({ x: from.x, z: INSIDE }), at({ x: door, z: INSIDE }), at({ x: door, z: FRONT }));
  }
  points.push(at({ x: to.x, z: FRONT }));
  if (to.z >= -1.4) {
    points.push(at(to));
  } else {
    const door = doorFor(to.x);
    points.push(at({ x: door, z: FRONT }), at({ x: door, z: INSIDE }),
      at({ x: to.x, z: INSIDE }), at(to));
  }
  return points.filter((point, index, array) =>
    !index || Math.hypot(point.x - array[index - 1].x, point.z - array[index - 1].z) > .001);
}

const at = (point: OfficePoint): OfficePoint => ({ x: point.x, z: point.z });

// Personal space: nobody walks through a colleague who is in the way. A
// walker either steps around them or pauses for a quick greeting instead.
export const PERSONAL_RADIUS = .62;

export function officeBlocked(point: OfficePoint, others: OfficePoint[], radius = PERSONAL_RADIUS) {
  return others.some(other => Math.hypot(point.x - other.x, point.z - other.z) < radius);
}

function safePoint(x: number, z: number): OfficePoint {
  let px = Math.max(-11.9, Math.min(11.9, x));
  let pz = z;
  if (pz < -1.4) {
    const room = px < -4.25 ? [-11.9, -4.35] : px > 4.25 ? [4.35, 11.9] : [-3.2, 3.2];
    px = Math.max(room[0], Math.min(room[1], px));
    pz = Math.max(-6.4, Math.min(-1.45, pz));
  } else {
    pz = Math.max(-1.35, Math.min(6.4, pz));
  }
  // Keep the sidestep off the meeting table as well.
  if (px > -10.6 && px < -5.4 && pz > .4 && pz < 3.6) pz = pz > 2 ? 3.75 : .25;
  return { x: px, z: pz };
}

// Reactive avoidance for the current frame. If the proposed step overlaps a
// colleague, try a bounded perpendicular sidestep (away from them) and keep
// the original step queued; if even that is crowded, simply wait and greet.
export function officeAvoidStep(
  from: OfficePoint,
  desired: OfficePoint,
  path: OfficePoint[],
  others: OfficePoint[],
): { point: OfficePoint; path: OfficePoint[]; greeting: boolean; blocker: number } {
  let blocker = -1, nearest = PERSONAL_RADIUS;
  others.forEach((other, index) => {
    const distance = Math.hypot(desired.x - other.x, desired.z - other.z);
    if (distance < nearest) { nearest = distance; blocker = index; }
  });
  if (blocker < 0 || Math.hypot(desired.x - from.x, desired.z - from.z) < .001) {
    return { point: desired, path, greeting: false, blocker: -1 };
  }
  const other = others[blocker];
  const dx = desired.x - from.x, dz = desired.z - from.z;
  const length = Math.hypot(dx, dz);
  const tx = dx / length, tz = dz / length;
  let px = -tz, pz = tx;
  if ((from.x - other.x) * px + (from.z - other.z) * pz < 0) { px = -px; pz = -pz; }
  // Step aside now, then queue one real detour that carries us past the
  // colleague before rejoining the original route. Queuing the tiny original
  // step instead would make the walker oscillate in place forever.
  const offset = PERSONAL_RADIUS + .33;
  const along = Math.max(0, (other.x - from.x) * tx + (other.z - from.z) * tz);
  for (const side of [1, -1]) {
    const sx = px * side, sz = pz * side;
    const candidate = safePoint(from.x + sx * offset, from.z + sz * offset);
    if (officeBlocked(candidate, others, PERSONAL_RADIUS * .9)) continue;
    const detour = safePoint(from.x + tx * (along + 1.05) + sx * offset,
      from.z + tz * (along + 1.05) + sz * offset);
    if (officeBlocked(detour, others, PERSONAL_RADIUS * .9)) continue;
    const rest = [candidate];
    if (Math.hypot(detour.x - candidate.x, detour.z - candidate.z) > .01) rest.push(detour);
    rest.push(...path);
    return { point: from, path: rest, greeting: true, blocker };
  }
  return { point: from, path, greeting: true, blocker };
}

export function officeStep(from: OfficePoint, path: OfficePoint[], seconds: number) {
  let point = { ...from }, remaining = Math.max(0, seconds) * 1.65, rotation = 0;
  const rest = path.slice();
  while (rest.length) {
    const next = rest[0], dx = next.x - point.x, dz = next.z - point.z, distance = Math.hypot(dx, dz);
    if (distance < .001) { rest.shift(); continue; }
    rotation = Math.atan2(dx, dz);
    if (remaining < distance) {
      const ratio = remaining / distance;
      point = { x: point.x + dx * ratio, z: point.z + dz * ratio };
      break;
    }
    remaining -= distance; point = { ...next }; rest.shift();
  }
  return { ...point, rotation, path: rest, moving: rest.length > 0 };
}
