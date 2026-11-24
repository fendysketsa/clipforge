export type OfficePoint = { x: number; z: number; y?: number };
export type OfficeActivity = "desk" | "walk" | "meeting" | "coffee" | "lounge" | "game" | "toilet" | "stairs" | "reading";
export const FLOOR_HEIGHT = 3.6;
const STAIRS = { x: -12.9, z: -1.6 };
const STAIRS_TOP_Z = -5;
const UPPER_LANDING_Z = -1.55;

export const OFFICE_PEOPLE = [
  { id: "production", name: "Raka", role: "Produksi", color: "#4f9383", desk: { x: -7.5, z: -4.3 }, door: -6 },
  { id: "quality", name: "Naya", role: "Quality control", color: "#9880bd", desk: { x: -2.5, z: -4.3 }, door: 0 },
  { id: "distribution", name: "Dimas", role: "Distribusi", color: "#588db7", desk: { x: 2.5, z: -4.3 }, door: 0 },
  { id: "recovery", name: "Bima", role: "Pemulihan", color: "#c28d54", desk: { x: 7.5, z: -4.3 }, door: 6 },
  { id: "cleanup", name: "Sari", role: "Pengelola aset", color: "#7c9b5b", desk: { x: -7.5, z: 4.2 }, door: -6 },
  { id: "facebook", name: "Mika", role: "Facebook", color: "#697db8", desk: { x: 7.5, z: 4.2 }, door: 6 },
] as const;

// Waiting people are spread across real places instead of gathering in one spot.
const BLOCKED_SPOTS: (OfficePoint & { activity: OfficeActivity })[] = [
  { x: -9.2, z: -4.8, activity: "meeting" },
  { x: -6.8, z: -4.8, activity: "meeting" },
  { x: -8.6, z: -5, y: FLOOR_HEIGHT, activity: "game" },
  { x: -5.9, z: -5, y: FLOOR_HEIGHT, activity: "game" },
  { x: 6.6, z: -5, y: FLOOR_HEIGHT, activity: "toilet" },
  { x: 9.2, z: -5, y: FLOOR_HEIGHT, activity: "toilet" },
];
const IDLE_SPOTS: (OfficePoint & { activity: OfficeActivity })[] = [
  { x: -2.4, z: 3.4, activity: "lounge" },
  { x: 2.4, z: 3.4, activity: "coffee" },
  { x: -8.4, z: 3.6, activity: "reading" },
  { x: 8.4, z: 3.6, activity: "coffee" },
  { x: -7.2, z: -5, y: FLOOR_HEIGHT, activity: "game" },
  { x: 7.9, z: -5, y: FLOOR_HEIGHT, activity: "toilet" },
];
const QUEUE_SPOTS: (OfficePoint & { activity: OfficeActivity })[] = [
  { x: 6.6, z: 4.1, activity: "coffee" },
  { x: 8.4, z: 3.6, activity: "coffee" },
  { x: -5.9, z: -5, y: FLOOR_HEIGHT, activity: "game" },
  { x: -8.6, z: -5, y: FLOOR_HEIGHT, activity: "game" },
  { x: -1, z: -4.8, y: FLOOR_HEIGHT, activity: "reading" },
  { x: 0, z: 4.4, activity: "lounge" },
];

export function officeDestination(index: number, state: string): OfficePoint & { activity: OfficeActivity } {
  const person = OFFICE_PEOPLE[index];
  if (state === "blocked") return BLOCKED_SPOTS[index % BLOCKED_SPOTS.length];
  if (state === "queued") return QUEUE_SPOTS[index % QUEUE_SPOTS.length];
  if (state === "idle") return IDLE_SPOTS[index % IDLE_SPOTS.length];
  return { ...person.desk, activity: "desk" };
}

const at = (point: OfficePoint, y = point.y ?? 0): OfficePoint => ({ x: point.x, z: point.z, y });

/** Doorways and one shared staircase connect both floors; traffic can pass both ways. */
export function officePath(from: OfficePoint, to: OfficePoint): OfficePoint[] {
  const fromY = from.y ?? 0;
  const toY = to.y ?? 0;
  const doorFor = (x: number) => x < -3 ? -6 : x > 3 ? 6 : 0;
  const lower = (point: OfficePoint): OfficePoint[] => {
    const level = point.y ?? 0;
    const door = doorFor(point.x);
    if (level === 0) {
      if (point.z >= -1.4) return [at(point, 0), at({ x: point.x, z: .2 }, 0)];
      return [at(point, 0), at({ x: point.x, z: -2.4 }, 0), at({ x: door, z: -2.4 }, 0), at({ x: door, z: .2 }, 0)];
    }
    return [at(point, level), at({ x: door, z: point.z }, level), at({ x: door, z: UPPER_LANDING_Z }, level)];
  };
  const route = [...lower(from)];
  if (fromY !== toY) {
    const top = at({ x: STAIRS.x, z: STAIRS_TOP_Z }, FLOOR_HEIGHT);
    if (fromY === 0) route.push(at({ x: STAIRS.x, z: .2 }, 0), at(STAIRS, 0), top,
      at({ x: STAIRS.x, z: UPPER_LANDING_Z }, FLOOR_HEIGHT));
    else route.push(at({ x: STAIRS.x, z: UPPER_LANDING_Z }, FLOOR_HEIGHT), top, at(STAIRS, 0));
    if (toY === 0) route.push(at({ x: STAIRS.x, z: .2 }, 0));
    else route.push(at({ x: doorFor(to.x), z: UPPER_LANDING_Z }, FLOOR_HEIGHT));
  }
  route.push(...lower(to).reverse());
  route.push(at(to, toY));
  return route.filter((point, index, array) =>
    !index || Math.hypot(point.x - array[index - 1].x, point.z - array[index - 1].z,
      (point.y ?? 0) - (array[index - 1].y ?? 0)) > .001);
}

export function officeStep(from: OfficePoint, path: OfficePoint[], seconds: number) {
  let point: OfficePoint = { ...from, y: from.y ?? 0 };
  let remaining = Math.max(0, seconds) * 1.65, rotation = 0;
  const rest = path.slice();
  while (rest.length) {
    const next = { ...rest[0], y: rest[0].y ?? 0 };
    const dx = next.x - point.x, dz = next.z - point.z, dy = next.y - (point.y ?? 0);
    const distance = Math.hypot(dx, dz, dy);
    if (distance < .001) { rest.shift(); continue; }
    rotation = Math.atan2(dx, dz);
    if (remaining < distance) {
      const ratio = remaining / distance;
      point = { x: point.x + dx * ratio, z: point.z + dz * ratio, y: (point.y ?? 0) + dy * ratio };
      break;
    }
    remaining -= distance; point = next; rest.shift();
  }
  return { ...point, rotation, path: rest, moving: rest.length > 0 };
}
