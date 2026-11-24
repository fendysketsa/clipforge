import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { OFFICE_PEOPLE, officeDestination, officePath, officeStep, type OfficePoint, type OfficeActivity } from "./officeChoreography";

export type OfficeProjection = { id: string; x: number; y: number; activity: OfficeActivity };
export const OFFICE_AREAS = [
  { id: "meeting", label: "Ruang rapat", x: -8, z: -5.9 },
  { id: "creative", label: "Produksi & QC", x: 0, z: -5.9 },
  { id: "media", label: "Distribusi & pemulihan", x: 8, z: -5.9 },
  { id: "assets", label: "Studio sosial & aset", x: -7.5, z: 5.8 },
  { id: "lounge", label: "Lounge", x: .3, z: 5.8 },
  { id: "pantry", label: "Coffee bar", x: 8, z: 5.8 },
];

/** Procedural models are bundled with the app: no external models, textures or CDN. */
export function createOfficeScene(host: HTMLElement, project: (people: OfficeProjection[], areas: OfficeProjection[]) => void) {
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);
  host.appendChild(renderer.domElement);
  const camera = new THREE.OrthographicCamera(-18, 18, 12, -12, .1, 150);
  camera.position.set(18, 24, 30);
  camera.lookAt(0, 0, 0);
  const ambient = new THREE.HemisphereLight(0xf8fbff, 0xb2a38e, 2.5);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xfff3d9, 3.2);
  sun.position.set(-6, 19, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -19, right: 19, top: 17, bottom: -17, far: 70 });
  sun.shadow.normalBias = .035; sun.shadow.bias = -.00015;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xcbdfff, 1.4); fill.position.set(10, 7, -10); scene.add(fill);
  const fixed = new THREE.Group(); scene.add(fixed);
  const materials = new Map<string, THREE.MeshStandardMaterial>();
  const geometries = new Set<THREE.BufferGeometry>();
  const textures: THREE.Texture[] = [];
  function material(color: string, opacity = 1) {
    const key = color + opacity;
    if (!materials.has(key)) materials.set(key, new THREE.MeshStandardMaterial({ color, roughness: .78,
      transparent: opacity < 1, opacity, depthWrite: opacity === 1, metalness: opacity < 1 ? .1 : 0 }));
    return materials.get(key)!;
  }
  function mesh(geometry: THREE.BufferGeometry, color: string, x: number, y: number, z: number, parent: THREE.Object3D = fixed, opacity = 1) {
    geometries.add(geometry);
    const object = new THREE.Mesh(geometry, material(color, opacity));
    object.position.set(x, y, z); object.castShadow = opacity === 1; object.receiveShadow = true;
    parent.add(object); return object;
  }
  function box(x: number, y: number, z: number, w: number, h: number, d: number, color: string, parent: THREE.Object3D = fixed, opacity = 1) {
    return mesh(new THREE.BoxGeometry(w, h, d), color, x, y, z, parent, opacity);
  }
  function cylinder(x: number, y: number, z: number, r: number, h: number, color: string, parent: THREE.Object3D = fixed, top = r) {
    return mesh(new THREE.CylinderGeometry(top, r, h, 12), color, x, y, z, parent);
  }
  function sphere(x: number, y: number, z: number, r: number, color: string, parent: THREE.Object3D = fixed) {
    return mesh(new THREE.SphereGeometry(r, 12, 8), color, x, y, z, parent);
  }
  function board(text: string, x: number, y: number, z: number, width: number, background = "#25443d", ink = "#faf4e6") {
    const canvas = document.createElement("canvas"); canvas.width = 768; canvas.height = 192;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = background; ctx.fillRect(0, 0, 768, 192);
    ctx.fillStyle = ink; ctx.font = "600 54px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, 384, 96, 710);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture);
    const geometry = new THREE.PlaneGeometry(width, width / 4); geometries.add(geometry);
    const mat = new THREE.MeshBasicMaterial({ map: texture });
    const sign = new THREE.Mesh(geometry, mat); sign.position.set(x, y, z); scene.add(sign);
    return mat;
  }
  const signMaterials: THREE.Material[] = [];
  // Floating slab and individual oak boards, with the front and roof removed.
  box(0, -.42, 0, 24.6, .75, 14.6, "#a99378");
  box(0, -.05, 0, 24.4, .14, 14.4, "#efe2c8");
  const woods = ["#c9ac82", "#d8bc94", "#cfb18a", "#dec49e", "#d1b28a"];
  for (let row = 0; row < 28; row++) for (let col = 0; col < 12; col++) {
    const x = -11 + col * 2, z = -6.75 + row * .5;
    box(x, .04, z, 1.97, .06, .48, woods[(row * 3 + col) % woods.length]);
  }
  box(0, 1.55, -7, 24.3, 3.1, .18, "#f0ecdf");
  box(-12, 1.55, -3.5, .18, 3.1, 7, "#e2ded0");
  box(-12, .45, 3.5, .18, .9, 7, "#e2ded0");
  box(0, .15, -6.84, 24, .22, .12, "#b7a182");
  // Skyline and large blue windows across the back of the office.
  for (let i = 0; i < 9; i++) {
    box(-3.35 + i * 1.7, 1.95, -6.87, 1.59, 1.92, .035, "#b4d3d8");
    box(-3.35 + i * 1.7, 1.05, -6.81, 1.6, .09, .09, "#698b89");
    box(-4.2 + i * 1.7, 1.95, -6.8, .055, 2, .08, "#53676a");
    box(-3.65 + i * 1.7, 1.46, -6.82, .6, .75 + (i % 3) * .22, .015, "#9bbbc4");
  }
  signMaterials.push(board("RYUUNDY / CREATIVE STUDIO", -8, 2.55, -6.86, 6));
  // Glass partitions; corridor-facing walls have a real 1.8m door opening.
  function glassX(x: number, z1: number, z2: number) {
    box(x, 1.35, (z1 + z2) / 2, .055, 2.7, z2 - z1, "#a1c8c5", fixed, .18);
    [z1, z2, (z1 + z2) / 2].forEach(z => box(x, 1.35, z, .06, 2.7, .065, "#536b69"));
    box(x, 2.7, (z1 + z2) / 2, .07, .055, z2 - z1, "#536b69");
    box(x, .12, (z1 + z2) / 2, .08, .12, z2 - z1, "#536b69");
  }
  function glassFront(start: number, end: number, door: number) {
    for (const [a, b] of [[start, door - .9], [door + .9, end]]) {
      box((a + b) / 2, 1.15, -1.4, b - a, 2.3, .045, "#9cc4c2", fixed, .16);
      [a, b].forEach(x => box(x, 1.15, -1.4, .055, 2.3, .065, "#607773"));
      box((a + b) / 2, 2.3, -1.4, b - a, .055, .07, "#607773");
      box((a + b) / 2, .12, -1.4, b - a, .09, .07, "#607773");
    }
  }
  glassX(-4.25, -6.8, -1.4); glassX(4.25, -6.8, -1.4);
  glassFront(-11.8, -4.25, -6); glassFront(-4.25, 4.25, 0); glassFront(4.25, 11.8, 7.8);
  // Meeting room, chairs, whiteboard with sticky notes and wall clock.
  box(-8, .12, -3.8, 6.7, .025, 4.4, "#8daba1");
  box(-8, 1.05, -4.2, 2.3, .16, 2.7, "#ba9671");
  box(-8, .5, -4.2, 1.5, 1, 1.8, "#596e67");
  function chair(x: number, z: number, rotation = 0, color = "#4f655f") {
    const group = new THREE.Group(); group.position.set(x, 0, z); group.rotation.y = rotation; fixed.add(group);
    box(0, .64, 0, .64, .18, .67, color, group);
    box(0, 1.02, .29, .66, .65, .12, color, group);
    cylinder(0, .3, 0, .055, .6, "#485451", group);
    box(0, .1, 0, .7, .07, .08, "#485451", group); box(0, .1, 0, .08, .07, .7, "#485451", group);
  }
  for (const z of [-4.9, -3.5]) { chair(-9.65, z, Math.PI / 2); chair(-6.35, z, -Math.PI / 2); }
  box(-11.84, 2, -4.5, .06, 1.45, 2.4, "#faf9f1");
  for (let i = 0; i < 6; i++) box(-11.79, 1.8 + (i % 2) * .45, -5.3 + Math.floor(i / 2) * .6, .025, .27, .38, ["#eacb79", "#91b6a2", "#d4a18f"][i % 3]);
  const clock = cylinder(-4.75, 2.5, -6.83, .31, .08, "#344d47"); clock.rotation.x = Math.PI / 2;
  const face = cylinder(-4.75, 2.5, -6.77, .26, .015, "#faf5e7"); face.rotation.x = Math.PI / 2;
  box(-4.75, 2.57, -6.73, .025, .18, .02, "#344d47"); box(-4.68, 2.5, -6.72, .17, .025, .02, "#344d47");
  // Workstations: screens, keyboards, desk lamps, notebooks, mugs and chairs.
  function desk(x: number, z: number, color: string, reverse = false) {
    const group = new THREE.Group(); fixed.add(group); group.position.set(x, 0, z); group.rotation.y = reverse ? Math.PI : 0;
    box(0, 1.02, 0, 2.55, .14, 1.15, "#ead9b8", group);
    for (const dx of [-1.05, 1.05]) for (const dz of [-.4, .4]) box(dx, .48, dz, .08, 1, .08, "#4e5c58", group);
    box(0, 1.58, -.22, 1.15, .74, .09, "#354c48", group);
    box(0, 1.58, -.164, 1.02, .61, .02, "#b6d3cc", group);
    box(-.29, 1.57, -.147, .3, .38, .012, color, group);
    for (let i = 0; i < 4; i++) box(.18, 1.78 - i * .13, -.145, .47 - i % 2 * .12, .035, .012, "#f0f4de", group);
    box(0, 1.19, -.22, .07, .2, .07, "#354c48", group); box(0, 1.1, -.22, .48, .03, .28, "#354c48", group);
    box(-.07, 1.11, .29, .72, .025, .25, "#596e67", group);
    cylinder(.89, 1.2, .27, .1, .24, "#f6f0de", group); cylinder(.89, 1.33, .27, .075, .007, "#594237", group);
    box(-.95, 1.12, .13, .35, .045, .45, color, group);
    chair(x, z + (reverse ? -1 : 1), reverse ? Math.PI : 0);
  }
  desk(-1.9, -4.4, "#4f9383"); desk(1.8, -4.4, "#9880bd");
  desk(6.1, -4.4, "#588db7"); desk(9.5, -4.4, "#c28d54");
  desk(-8.8, 4.3, "#7c9b5b", true); desk(-5.5, 4.3, "#697db8", true);
  // Storage and open shelving along the social studio.
  box(-11.3, .72, 4.7, .8, 1.4, 3.2, "#c5a17b");
  for (let i = 0; i < 5; i++) box(-10.87, .8, 3.5 + i * .55, .04, .92, .035, "#9e805e");
  // Lounge, rug, sofa, coffee table and central tree planter.
  box(.3, .11, 4.5, 5.7, .025, 3.5, "#dfd7c2");
  box(.3, .47, 5.55, 3.8, .74, 1.05, "#6e8b72");
  box(.3, .94, 5.94, 3.8, .8, .3, "#6e8b72");
  for (const x of [-1.45, 2.05]) box(x, .8, 5.5, .3, .65, 1.2, "#607f66");
  for (let i = 0; i < 3; i++) box(-.85 + i * 1.15, .9, 5.4, 1.07, .2, .84, "#92a48a");
  cylinder(.3, .52, 3.55, .78, .13, "#be9c72"); cylinder(.3, .26, 3.55, .12, .5, "#4b5e55");
  box(.25, .6, 3.55, .5, .045, .36, "#f3eee2");
  cylinder(-3.2, .4, 3.9, .7, .7, "#f1e8d6");
  cylinder(-3.2, 1.2, 3.9, .14, 1.7, "#897456");
  for (let i = 0; i < 7; i++) sphere(-3.2 + Math.sin(i * 2.4) * .52, 2.15 + (i % 3) * .25, 3.9 + Math.cos(i * 2.4) * .45, .68, i % 2 ? "#799568" : "#8da577");
  // Coffee bar, slatted oak backing, espresso machine and stools.
  box(8.3, .55, 5.65, 5, 1.1, 1.15, "#bc9870");
  box(8.3, 1.17, 5.65, 5.2, .15, 1.35, "#efdfc0");
  for (let i = 0; i < 20; i++) box(5.9 + i * .25, .55, 6.24, .08, 1.1, .04, "#96734f");
  box(7, 1.57, 5.65, .85, .7, .65, "#3e4c47"); box(7, 1.6, 5.99, .63, .38, .03, "#a2b0a6");
  for (const x of [6.8, 7.2, 8.7]) cylinder(x, 1.36, 5.89, .09, .2, "#faf3e5");
  box(9.35, 1.47, 5.65, .7, .45, .6, "#c6ae87");
  for (const x of [6.4, 8.2, 10]) { cylinder(x, .88, 4.4, .32, .14, "#5f776b"); cylinder(x, .43, 4.4, .055, .8, "#495e53"); }
  // Plants and pendant lights give each area a lived-in scale.
  function plant(x: number, z: number) {
    cylinder(x, .3, z, .3, .6, "#525e50", fixed, .4);
    for (let i = 0; i < 5; i++) {
      const leaf = sphere(x + Math.sin(i * 2.4) * .2, .9 + i % 2 * .28, z + Math.cos(i * 2.4) * .2, .28, "#6c915c");
      leaf.scale.set(.7, 1.7, .65);
    }
  }
  [[-10.9, -5.9], [3.5, -5.9], [11, -5.9], [-10.9, 1.6], [11, 2.7]].forEach(([x, z]) => plant(x, z));
  for (const x of [-8, 0, 8]) {
    cylinder(x, 3.9, -4, .018, .65, "#596659");
    cylinder(x, 3.5, -4, .47, .23, "#dfc997", fixed, .2);
  }
  // Merge static opaque furniture by material: keep the animation inexpensive.
  fixed.updateMatrixWorld(true);
  const buckets = new Map<THREE.Material, THREE.BufferGeometry[]>();
  const opaque: THREE.Mesh[] = [];
  fixed.traverse(object => {
    if (!(object instanceof THREE.Mesh) || Array.isArray(object.material) || object.material.transparent) return;
    const transformed = object.geometry.clone().applyMatrix4(object.matrixWorld);
    const list = buckets.get(object.material) || []; list.push(transformed); buckets.set(object.material, list); opaque.push(object);
  });
  opaque.forEach(object => object.removeFromParent());
  for (const [mat, parts] of buckets) {
    const geometry = mergeGeometries(parts); parts.forEach(part => part.dispose());
    if (!geometry) continue;
    geometries.add(geometry); const object = new THREE.Mesh(geometry, mat); object.castShadow = true; object.receiveShadow = true; scene.add(object);
  }
  // Six distinct articulated employees, with feet, eyes, hair and a small work badge.
  const people = OFFICE_PEOPLE.map((person, index) => {
    const group = new THREE.Group(); scene.add(group);
    const body = new THREE.Group(); group.add(body);
    box(0, .91, 0, .43, .56, .27, person.color, body);
    box(0, 1.17, .15, .1, .14, .015, "#eee5cc", body);
    const skin = ["#d6a17f", "#ba8769", "#e2b894"][index % 3];
    const head = sphere(0, 1.46, 0, .23, skin, body); head.scale.y = 1.12;
    const hair = sphere(0, 1.58, -.035, .235, index % 3 ? "#403b32" : "#66513e", body); hair.scale.set(1, .65, 1);
    if (index % 2) box(0, 1.4, -.16, .42, .38, .15, "#403b32", body);
    for (const x of [-.085, .085]) sphere(x, 1.47, .205, .022, "#29362f", body);
    const legs = [-1, 1].map(side => {
      const limb = new THREE.Group(); limb.position.set(side * .12, .67, 0); body.add(limb);
      box(0, -.24, 0, .14, .48, .16, "#465650", limb); box(0, -.47, .055, .18, .13, .27, "#303f37", limb); return limb;
    });
    const arms = [-1, 1].map(side => {
      const limb = new THREE.Group(); limb.position.set(side * .28, 1.13, 0); body.add(limb);
      box(0, -.18, 0, .14, .39, .16, person.color, limb); sphere(0, -.4, 0, .085, skin, limb); return limb;
    });
    const mug = cylinder(.31, .76, .13, .075, .17, "#f7e8d0", body); mug.visible = false;
    return { group, body, legs, arms, mug, point: { ...person.desk } as OfficePoint,
      path: [] as OfficePoint[], destination: "", rotation: person.desk.z > 0 ? 0 : Math.PI };
  });
  let width = 1, height = 1, zoom = 1, night = false;
  let lastSeconds = 0, lastStates: Record<string, string> = {};
  const projected = new THREE.Vector3();
  function resize() {
    width = Math.max(host.clientWidth, 1); height = Math.max(host.clientHeight, 1);
    renderer.setSize(width, height);
    const aspect = width / height;
    const vertical = Math.max(11.6, 17.4 / aspect) / zoom;
    camera.left = -vertical * aspect; camera.right = vertical * aspect;
    camera.top = vertical; camera.bottom = -vertical; camera.updateProjectionMatrix();
    render(lastSeconds, night, lastStates);
  }
  function point(x: number, y: number, z: number) {
    projected.set(x, y, z).project(camera);
    return { x: (projected.x * .5 + .5) * width, y: (-projected.y * .5 + .5) * height };
  }
  function render(seconds: number, isNight: boolean, states: Record<string, string> = {}) {
    const delta = Math.min(Math.max(seconds - lastSeconds, 0), .12);
    lastSeconds = seconds; lastStates = states;
    camera.updateMatrixWorld();
    if (night !== isNight) { night = isNight; ambient.intensity = night ? 1.9 : 2.5; sun.intensity = night ? 1.8 : 3.2; }
    const projections = people.map((person, index) => {
      const profile = OFFICE_PEOPLE[index];
      const state = states[profile.id] || "unavailable";
      const target = officeDestination(index, state);
      const destination = `${target.x}:${target.z}`;
      if (state !== "unavailable" && destination !== person.destination) {
        person.path = Math.hypot(target.x-person.point.x,target.z-person.point.z) > .01 ? officePath(person.point, target) : [];
        person.destination = destination;
      }
      if (state !== "unavailable" && person.path.length && delta > 0) {
        const step = officeStep(person.point, person.path, delta);
        person.point = { x:step.x,z:step.z }; person.path = step.path; person.rotation = step.rotation;
      }
      if (!person.path.length) person.rotation = target.activity === "desk" ? (profile.desk.z > 0 ? 0 : Math.PI) : index % 2 ? -Math.PI / 2 : Math.PI / 2;
      const pose = { ...person.point, rotation: person.rotation, activity: person.path.length && state !== "unavailable" ? "walk" as const : target.activity };
      person.group.position.set(pose.x, 0, pose.z); person.group.rotation.y = pose.rotation;
      person.body.position.y = pose.activity === "walk" ? Math.abs(Math.sin(seconds * 8)) * .045 : pose.activity === "desk" ? -.12 : 0;
      person.legs.forEach((leg, side) => leg.rotation.x = pose.activity === "walk" ? Math.sin(seconds * 8 + side * Math.PI) * .52 : 0);
      person.arms.forEach((arm, side) => {
        arm.rotation.x = pose.activity === "walk" ? Math.sin(seconds * 8 + side * Math.PI + Math.PI) * .4
          : pose.activity === "meeting" ? -.5 + Math.sin(seconds * 2.5 + side) * .25
            : pose.activity === "desk" && state === "running" ? -.55 + Math.sin(seconds * 5 + side) * .08 : -.2;
      });
      person.mug.visible = pose.activity === "coffee";
      return { id: OFFICE_PEOPLE[index].id, ...point(pose.x, 2.15, pose.z), activity: pose.activity };
    });
    renderer.render(scene, camera);
    project(projections, OFFICE_AREAS.map(area => ({ id: area.id, ...point(area.x, .25, area.z), activity: "desk" })));
  }
  const observer = new ResizeObserver(resize); observer.observe(host); resize();
  return {
    render,
    zoom(value: number) { zoom = value; resize(); },
    dispose() {
      observer.disconnect(); geometries.forEach(geometry => geometry.dispose());
      materials.forEach(mat => mat.dispose()); signMaterials.forEach(mat => mat.dispose()); textures.forEach(texture => texture.dispose());
      renderer.dispose(); renderer.domElement.remove();
    },
  };
}
