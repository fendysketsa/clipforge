export type OfficePoint = { x: number; z: number; y?: number };
export type OfficeActivity = "desk" | "walk" | "meeting" | "coffee" | "lounge" | "sofa" | "reading" | "write" | "call" | "copy" | "snack" | "cards";

// One floor only. Every working spot is in the open front area (z > -1.4),
// so nobody ever has to cross the glass partition or a wall to do their job.
export const OFFICE_PEOPLE = [
  { id: "production", name: "Raka", role: "Produksi", color: "#4f9383", desk: { x: -2.6, z: 2.2 } },
  { id: "quality", name: "Naya", role: "Quality control", color: "#9880bd", desk: { x: -0.6, z: 2.2 } },
  { id: "distribution", name: "Dimas", role: "Distribusi", color: "#588db7", desk: { x: 1.4, z: 2.2 } },
  { id: "recovery", name: "Bima", role: "Pemulihan", color: "#c28d54", desk: { x: 3.4, z: 2.2 } },
  { id: "cleanup", name: "Sari", role: "Pengelola aset", color: "#7c9b5b", desk: { x: -8.8, z: 4.3 } },
  { id: "facebook", name: "Mika", role: "Facebook", color: "#697db8", desk: { x: -5.5, z: 4.3 } },
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
    { x: -10.3, z: 1, activity: "meeting" },
    { x: -5.7, z: 1, activity: "meeting" },
    { x: -10.3, z: 2.4, activity: "meeting" },
    { x: -5.7, z: 2.4, activity: "meeting" },
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

export function officeDestination(index: number, state: string): OfficePoint & { activity: OfficeActivity } {
  if (state === 'queued' || state === 'blocked' || state === 'idle') return SPOTS[state][index % SPOTS[state].length];
  return { ...OFFICE_PEOPLE[index].desk, activity: 'desk' };
}

// Ground floor only: routes stay in the open front area and never touch glass.
export function officePath(from: OfficePoint, to: OfficePoint): OfficePoint[] {
  const lane = 3.8 + (OFFICE_PEOPLE.findIndex(row => Math.abs(row.desk.x - from.x) < .01 && Math.abs(row.desk.z - from.z) < .01) % 3) * .35;
  const points: OfficePoint[] = [at(from)];
  if (Math.abs(from.z - to.z) > .01) points.push(at({ x: from.x, z: lane }));
  if (Math.abs(from.x - to.x) > .01) points.push(at({ x: to.x, z: lane }));
  points.push(at(to));
  return points.filter((point, index, array) =>
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
