export type OfficePoint = { x: number; z: number; y?: number };
export type OfficeActivity = "desk" | "walk" | "meeting" | "briefing" | "observing" | "notice" | "coffee" | "lounge" | "sofa" | "reading" | "write" | "call" | "copy" | "snack" | "cards";

// One floor only. Every working spot is in the open front area (z > -1.4),
// so nobody ever has to cross the glass partition or a wall to do their job.
export const OFFICE_PEOPLE = [
  { id: "production", name: "Raka", role: "Produksi", color: "#4f9383", desk: { x: -2.5, z: -4 } },
  { id: "quality", name: "Naya", role: "Quality control", color: "#9880bd", desk: { x: .5, z: -4 } },
  { id: "distribution", name: "Dimas", role: "Distribusi", color: "#588db7", desk: { x: 6.5, z: -4 } },
  { id: "recovery", name: "Bima", role: "Pemulihan", color: "#c28d54", desk: { x: 9, z: -4 } },
  { id: "cleanup", name: "Sari", role: "Pengelola aset", color: "#7c9b5b", desk: { x: -9, z: -4 } },
  { id: "facebook", name: "Mika", role: "Facebook", color: "#697db8", desk: { x: -6.5, z: -4 } },
  { id: "director", name: "Pimpinan", role: "Direktur Studio", color: "#c99433", desk: { x: 2.5, z: -4 } },
] as const;

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

export function officeDestination(index: number, state: string): OfficePoint & { activity: OfficeActivity } {
  if (state === 'sofa') return { ...SOFA_SPOTS[index % SOFA_SPOTS.length], activity: 'sofa' };
  if (state === 'notice') return { ...TASK_BOARD_SPOTS[index % TASK_BOARD_SPOTS.length], activity: 'notice' };
  if (OFFICE_PEOPLE[index].id === 'director') {
    if (state === 'briefing') return { x: -8, z: 4.4, activity: 'briefing' };
    return { ...OFFICE_PEOPLE[index].desk, activity: 'observing' };
  }
  if (state === 'queued' || state === 'blocked' || state === 'idle') return SPOTS[state][index % SPOTS[state].length];
  return { ...OFFICE_PEOPLE[index].desk, activity: 'desk' };
}

// Ground floor rooms: leave through the room's own door, walk in the open
// front corridor, then enter the destination room through its door.
export function officePath(from: OfficePoint, to: OfficePoint): OfficePoint[] {
  const doorFor = (x: number) => x < -4.25 ? -11.2 : x > 4.25 ? 7.8 : 0;
  const exit = (point: OfficePoint): OfficePoint[] => {
    if (point.z >= -1.4) return [at(point)];
    const door = doorFor(point.x);
    return [at(point), at({ x: point.x, z: -2.4 }), at({ x: door, z: -2.4 }),
      at({ x: door, z: -1.5 }), at({ x: door, z: -1.35 })];
  };
  const enter = (point: OfficePoint): OfficePoint[] => {
    if (point.z >= -1.4) return [at(point)];
    const door = doorFor(point.x);
    return [at({ x: door, z: -1.35 }), at({ x: door, z: -1.5 }),
      at({ x: door, z: -2.4 }), at({ x: point.x, z: -2.4 }), at(point)];
  };
  const route = [...exit(from)];
  // The meeting table occupies x[-10.5,-5.5], z[.5,3.5]. Walk around its right
  // edge and along the front instead of cutting through the furniture.
  const nearMeeting = (point: OfficePoint) => point.z > -1.4 && point.z < 7 && point.x < -4.5 && point.x > -12;
  if (nearMeeting(from)) {
    route.push(at({ x: from.x, z: 4.4 }), at({ x: -4.6, z: 4.4 }), at({ x: -4.6, z: -1.35 }));
  }
  if (nearMeeting(to)) {
    const current = route[route.length - 1];
    route.push(at({ x: -4.6, z: current.z }), at({ x: -4.6, z: 4.4 }), at({ x: to.x, z: 4.4 }));
  }
  route.push(...enter(to));
  return route.filter((point, index, array) =>
    !index || Math.hypot(point.x - array[index - 1].x, point.z - array[index - 1].z) > .001);
}

const at = (point: OfficePoint): OfficePoint => ({ x: point.x, z: point.z });

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
