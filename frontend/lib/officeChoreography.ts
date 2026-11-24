export type OfficePoint = { x: number; z: number };
export type OfficeActivity = "desk" | "walk" | "meeting" | "coffee" | "lounge";
export const OFFICE_PEOPLE = [
  { id: "production", name: "Raka", role: "Produksi", color: "#4f9383", desk: { x: -1.9, z: -3.2 }, door: 0 },
  { id: "quality", name: "Naya", role: "Quality control", color: "#9880bd", desk: { x: 1.8, z: -3.2 }, door: 0 },
  { id: "distribution", name: "Dimas", role: "Distribusi", color: "#588db7", desk: { x: 6.1, z: -3.2 }, door: 7.8 },
  { id: "recovery", name: "Bima", role: "Pemulihan", color: "#c28d54", desk: { x: 9.5, z: -3.2 }, door: 7.8 },
  { id: "cleanup", name: "Sari", role: "Pengelola aset", color: "#7c9b5b", desk: { x: -8.8, z: 3.1 }, door: -7 },
  { id: "facebook", name: "Mika", role: "Facebook", color: "#697db8", desk: { x: -5.5, z: 3.1 }, door: -7 },
] as const;

export function officeDestination(index: number, state: string): OfficePoint & { activity: OfficeActivity } {
  const person = OFFICE_PEOPLE[index];
  if (state === "blocked") return { x: -8 + (index % 2 ? 1.65 : -1.65), z: -3.3 + Math.floor(index / 2) * .45, activity: "meeting" };
  if (state === "idle") {
    const places = [{x:-2,z:3}, {x:2.6,z:3}, {x:-2,z:4.7}, {x:2.6,z:4.7}, {x:-1.2,z:2}, {x:1.4,z:2}];
    return { ...places[index], activity: "lounge" };
  }
  return { ...person.desk, activity: "desk" };
}

/** Route changes only follow a new observed destination. Doors are shared by both directions. */
export function officePath(from: OfficePoint, to: OfficePoint): OfficePoint[] {
  const exit = (point: OfficePoint): OfficePoint[] => {
    if (point.z >= -1.4) return [point, { x: point.x, z: .15 }];
    const door = point.x < -4.25 ? -6 : point.x < 4.25 ? 0 : 7.8;
    return [point, { x: point.x, z: -2.1 }, { x: door, z: -2.1 }, { x: door, z: .15 }];
  };
  return [...exit(from), ...exit(to).reverse()].filter((point,index,array) => !index || Math.hypot(point.x-array[index-1].x,point.z-array[index-1].z) > .001);
}

export function officeStep(from: OfficePoint, path: OfficePoint[], seconds: number) {
  let point = { ...from }, remaining = Math.max(0, seconds) * 1.65, rotation = 0;
  const rest = path.slice();
  while (rest.length) {
    const next = rest[0], dx = next.x - point.x, dz = next.z - point.z, distance = Math.hypot(dx,dz);
    if (distance < .001) { rest.shift(); continue; }
    rotation = Math.atan2(dx,dz);
    if (remaining < distance) { point = { x:point.x+dx*remaining/distance,z:point.z+dz*remaining/distance }; break; }
    remaining -= distance; point = { ...next }; rest.shift();
  }
  return { ...point, rotation, path: rest, moving: rest.length > 0 };
}
