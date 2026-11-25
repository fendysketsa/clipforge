import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";
import { OFFICE_PEOPLE, directorState, officeAvoidStep, officeDestination, officeMotionFromWork, officePath, officeStep, patrolIndex, type OfficePoint, type OfficeActivity, type OfficeWorkCue } from "./officeChoreography";

export type OfficeProjection = { id: string; x: number; y: number; activity: OfficeActivity; chatWith?: string };
export const OFFICE_AREAS = [
  { id: "meeting", label: "Ruang rapat", x: -8, z: 1.7, y: 0 },
  { id: "creative", label: "Produksi & QC", x: 0, z: -5.9, y: 0 },
  { id: "media", label: "Distribusi & pemulihan", x: 8, z: -5.9, y: 0 },
  { id: "assets", label: "Studio sosial & aset", x: -7.5, z: 5.8, y: 0 },
  { id: "lounge", label: "Lounge", x: 0, z: 5.8, y: 0 },
  { id: "pantry", label: "Coffee bar", x: 7.5, z: 5.8, y: 0 },
];

/** Procedural models are bundled with the app: no external models, textures or CDN. */
export function createOfficeScene(host: HTMLElement,
  project: (people: OfficeProjection[], areas: OfficeProjection[]) => void,
  onZoomChange?: (value: number) => void) {
  const scene = new THREE.Scene();
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0x000000, 0);
  host.appendChild(renderer.domElement);
  const camera = new THREE.OrthographicCamera(-18, 18, 12, -12, .1, 150);
  const BASE_AZIMUTH = Math.atan2(18, 30);
  const CAMERA_RADIUS = Math.hypot(18, 30, 24);
  const BASE_ELEVATION = Math.atan2(24, Math.hypot(18, 30));
  let azimuth = BASE_AZIMUTH, elevation = BASE_ELEVATION;
  const focus = new THREE.Vector3(0, 0, 0);
  const pan = new THREE.Vector3();
  function refreshFocus() {
    const detail = Math.max(0, zoom - 1);
    focus.set(pan.x, pan.y + Math.min(3.1, detail * 2.4), pan.z - Math.min(3.2, detail * 2.4));
    updateCamera();
  }
  function updateCamera() {
    const flat = Math.cos(elevation) * CAMERA_RADIUS;
    camera.position.set(focus.x + Math.sin(azimuth) * flat,
      focus.y + Math.sin(elevation) * CAMERA_RADIUS,
      focus.z + Math.cos(azimuth) * flat);
    camera.lookAt(focus); camera.updateMatrixWorld();
  }
  updateCamera();
  const ambient = new THREE.HemisphereLight(0xf8fbff, 0xb2a38e, 2.5);
  scene.add(ambient);
  const sun = new THREE.DirectionalLight(0xfff3d9, 3.2);
  sun.position.set(-6, 19, 8); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -19, right: 19, top: 17, bottom: -17, far: 70 });
  sun.shadow.normalBias = .035; sun.shadow.bias = -.00015;
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0xcbdfff, 1.4); fill.position.set(10, 7, -10); scene.add(fill);
  // Lamps are created outside the merged static geometry so night mode can
  // switch each shade and its own warm light on independently.
  const lamps: { shade: THREE.MeshStandardMaterial; light: THREE.PointLight; pool: THREE.MeshBasicMaterial }[] = [];
  const lampMaterials: THREE.MeshStandardMaterial[] = [];
  const poolMaterials: THREE.MeshBasicMaterial[] = [];
  function pendant(x: number, z: number, level = 0) {
    const shade = new THREE.MeshStandardMaterial({ color: 0xffe7b4, emissive: 0xffc766, emissiveIntensity: 0.04,
      roughness: .5, transparent: true, opacity: .92 });
    lampMaterials.push(shade);
    const cone = new THREE.Mesh(new THREE.ConeGeometry(.52, .34, 16, 1, true), shade);
    cone.position.set(x, level + 3.32, z); cone.rotation.x = Math.PI; scene.add(cone);
    geometries.add(cone.geometry);
    const glow = new THREE.Mesh(new THREE.SphereGeometry(.16, 10, 8), shade);
    glow.position.set(x, level + 3.16, z); scene.add(glow); geometries.add(glow.geometry);
    const light = new THREE.PointLight(0xffd49a, 0, 14, 1.5);
    light.position.set(x, level + 3.05, z); scene.add(light);
    const pool = new THREE.MeshBasicMaterial({ color: 0xffcf7a, transparent: true, opacity: 0, depthWrite: false });
    poolMaterials.push(pool);
    const puddle = new THREE.Mesh(new THREE.CircleGeometry(2.1, 24), pool);
    puddle.rotation.x = -Math.PI / 2; puddle.position.set(x, level + .035, z + .7); scene.add(puddle);
    geometries.add(puddle.geometry);
    lamps.push({ shade, light, pool });
  }
  const fixed = new THREE.Group(); scene.add(fixed);
  const materials = new Map<string, THREE.MeshStandardMaterial>();
  const geometries = new Set<THREE.BufferGeometry>();
  const textures: THREE.Texture[] = [];
  const glowMaterials: THREE.MeshBasicMaterial[] = [];
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
  function board(text: string, x: number, y: number, z: number, width: number,
                 background = "#25443d", ink = "#faf4e6", rotationY = 0) {
    const canvas = document.createElement("canvas"); canvas.width = 768; canvas.height = 192;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = background; ctx.fillRect(0, 0, 768, 192);
    ctx.fillStyle = ink; ctx.font = "600 54px sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, 384, 96, 710);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; textures.push(texture);
    const geometry = new THREE.PlaneGeometry(width, width / 4); geometries.add(geometry);
    const mat = new THREE.MeshBasicMaterial({ map: texture });
    const sign = new THREE.Mesh(geometry, mat); sign.position.set(x, y, z); sign.rotation.y = rotationY; scene.add(sign);
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
  // Distinct floor zones give each department its own room identity. They are
  // thin inlays on the slab: no new obstacle on any walking route.
  box(-8.05, .082, -4.25, 7.4, .02, 5.2, "#3c6a61");
  box(-8.05, .094, -4.25, 7.1, .008, 4.9, "#47796f");
  box(.5, .082, -4.5, 4.6, .02, 4.8, "#756349");
  box(.5, .094, -4.5, 4.3, .008, 4.5, "#8a7452");
  box(8.1, .082, -4.25, 7.4, .02, 5.2, "#36586e");
  box(8.1, .094, -4.25, 7.1, .008, 4.9, "#426a82");
  box(0, 1.55, -7, 24.3, 3.1, .18, "#f0ecdf");
  // Left wall has a real opening at z=-1.6 so the staircase has an exit.
  box(-12, 1.55, -4.65, .18, 3.1, 4.7, "#e2ded0");
  box(-12, 1.55, -.45, .18, 3.1, .9, "#e2ded0");
  box(-12, .45, 3.5, .18, .9, 7, "#e2ded0");
  box(0, .15, -6.84, 24, .22, .12, "#b7a182");
  // Skyline and large blue windows across the back of the office.
  for (let i = 0; i < 9; i++) {
    box(-3.35 + i * 1.7, 1.95, -6.87, 1.59, 1.92, .035, "#b4d3d8");
    box(-3.35 + i * 1.7, 1.05, -6.81, 1.6, .09, .09, "#698b89");
    box(-4.2 + i * 1.7, 1.95, -6.8, .055, 2, .08, "#53676a");
    box(-3.65 + i * 1.7, 1.46, -6.82, .6, .75 + (i % 3) * .22, .015, "#9bbbc4");
  }
  // Per-room wainscot, vertical slats and signage: a real interior redesign,
  // all behind the desks so no route or collision test is affected.
  for (const [x, width, wall, accent] of [
    [-8.05, 7.3, "#2d5a52", "#79b6a5"],
    [.5, 4.3, "#6a5638", "#e0bd72"],
    [8.1, 7.3, "#2f5067", "#8fbcd6"],
  ] as const) {
    box(x, .48, -6.68, width, .96, .1, wall);
    for (let i = 0; i < Math.floor(width / .62); i++) {
      box(x - width / 2 + .36 + i * .62, 1.02, -6.62, .035, 1.35, .035, accent);
    }
    box(x, 3.06, -4.3, width - .3, .05, .12, accent);
  }
  // Room plaques live on the side walls, clear of the back-wall studio sign
  // and of the existing director plaque. They face into their own room.
  signMaterials.push(board("PRODUKSI & QC", -11.84, 2.42, -4.5, 3.4, "#23463f", "#f4efe0", Math.PI / 2));
  signMaterials.push(board("DISTRIBUSI & PEMULIHAN", 11.74, 2.42, -4.5, 4.4, "#234055", "#ecf4ff", -Math.PI / 2));
  signMaterials.push(board("RYUUNDY / CREATIVE STUDIO", -8, 2.55, -6.86, 6));
  // Glass partitions; corridor-facing walls have a real 1.8m door opening.
  function glassX(x: number, z1: number, z2: number) {
    const gap = 1.7, centre = -2.4;
    for (const [a, b] of [[z1, centre - gap / 2], [centre + gap / 2, z2]]) {
      if (b - a < .15) continue;
      box(x, 1.35, (a + b) / 2, .055, 2.7, b - a, "#a1c8c5", fixed, .18);
      [a, b].forEach(z => box(x, 1.35, z, .06, 2.7, .065, "#536b69"));
      box(x, 2.7, (a + b) / 2, .07, .055, b - a, "#536b69");
      box(x, .12, (a + b) / 2, .08, .12, b - a, "#536b69");
    }
    box(x, 2.55, centre, .08, .18, gap, "#536b69");
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
  glassFront(-12.2, -4.25, -11.2); glassFront(-4.25, 4.25, 0); glassFront(4.25, 11.8, 7.8);
  signMaterials.push(board("RAPAT / ASET", -11.2, 2.62, -1.32, 2.4, "#2d5a4e", "#ffeccb"));
  signMaterials.push(board("STUDIO SOSIAL", 0, 2.62, -1.32, 2.8, "#4a3f2f", "#ffe6ad"));
  signMaterials.push(board("DISTRIBUSI", 7.8, 2.62, -1.32, 2.4, "#234055", "#ecf4ff"));
  // Meeting room: a clearly marked open area in front-left of the ground floor.
  box(-8, .09, 2, 9, .1, 6, "#d8b98d");
  box(-8, .16, 2, 8.4, .06, 5.4, "#8daba1");
  box(-8, 1.12, 2, 5, .18, 3, "#c88754");
  box(-8, .62, 2, 3.6, .9, 2, "#7a8f84");
  box(-8, 1.23, 2, 4.2, .04, 2.2, "#f0d9b8");
  function chair(x: number, z: number, rotation = 0, color = "#4f655f") {
    const group = new THREE.Group(); group.position.set(x, 0, z); group.rotation.y = rotation; fixed.add(group);
    box(0, .64, 0, .72, .2, .72, color, group);
    box(0, 1.08, .34, .74, .7, .14, color, group);
    cylinder(0, .3, 0, .06, .6, "#485451", group);
    box(0, .1, 0, .74, .08, .08, "#485451", group); box(0, .1, 0, .08, .08, .74, "#485451", group);
  }
  for (const z of [1, 2.4]) {
    chair(-11.2, z, Math.PI / 2); chair(-4.8, z, Math.PI / 2);
  }
  chair(-8, .1, Math.PI); chair(-8, 3.9, 0);
  box(-11.84, 2.1, 1.9, .07, 1.7, 3.1, "#faf9f1");
  for (let i = 0; i < 6; i++) box(-11.79, 1.9 + (i % 2) * .5, .8 + Math.floor(i / 2) * .8, .03, .32, .45, ["#eacb79", "#91b6a2", "#d4a18f"][i % 3]);
  // The meeting room is now a defined zone with its own feature wall and light.
  box(-11.72, 2.1, 1.9, .05, 1.8, 3.2, "#2d5a4e");
  box(-8, .105, .15, 8.2, .02, .08, "#79b6a5");
  box(-8, .105, 3.85, 8.2, .02, .08, "#79b6a5");
  pendant(-8, 2, .3);
  signMaterials.push(board("RUANG RAPAT", -8, 3.15, 1.9, 4.6, "#2d5a4e", "#ffeccb"));
  signMaterials.push(board("RYUUNDY / RUANG PIMPINAN", 0.4, 2.95, -6.75, 6, "#4a3f2f", "#ffe6ad"));
  // Task board: the notices and labels sit on the FRONT face of the panel.
  box(7.4, 1.55, 1.6, .12, 2.7, 3.4, "#b9a888");
  box(7.47, 1.55, 1.6, .02, 2.4, 3.1, "#f7f2e3");
  box(7.49, .35, 1.6, .02, .05, 2.9, "#d8c8a4");
  signMaterials.push(board("PAPAN TUGAS", 7.53, 2.62, 1.6, 2.2, "#2d5a4e", "#ffeccb", Math.PI / 2));
  for (const [index, [label, colour]] of [
    ["PRODUKSI", "#dbe8dd"], ["QUALITY CONTROL", "#e7e0ef"],
    ["DISTRIBUSI", "#dbe6f0"], ["FACEBOOK", "#eee1cd"], ["PEMULIHAN", "#e5e8d5"],
  ].entries()) {
    const y = 2.08 - index * .4;
    box(7.5, y, 1.6, .03, .34, 2.66, colour);
    box(7.525, y, .42, .012, .14, .1, "#6f8f7e");
    signMaterials.push(board(label, 7.53, y, 1.7, 2.3, colour, "#2c4a40", Math.PI / 2));
  }
  const clock = cylinder(-4.75, 2.5, -6.83, .31, .08, "#344d47"); clock.rotation.x = Math.PI / 2;
  const face = cylinder(-4.75, 2.5, -6.77, .26, .015, "#faf5e7"); face.rotation.x = Math.PI / 2;
  box(-4.75, 2.57, -6.73, .025, .18, .02, "#344d47"); box(-4.68, 2.5, -6.72, .17, .025, .02, "#344d47");
  // Workstations: screens, keyboards, desk lamps, notebooks, mugs and chairs.
  const deskScreens: THREE.MeshBasicMaterial[] = [];
  function desk(x: number, z: number, color: string, reverse = false) {
    const group = new THREE.Group(); fixed.add(group); group.position.set(x, 0, z); group.rotation.y = reverse ? Math.PI : 0;
    box(0, 1.02, 0, 2.55, .14, 1.15, "#ead9b8", group);
    for (const dx of [-1.05, 1.05]) for (const dz of [-.4, .4]) box(dx, .48, dz, .08, 1, .08, "#4e5c58", group);
    box(0, 1.58, -.22, 1.15, .74, .09, "#354c48", group);
    box(0, 1.58, -.164, 1.02, .61, .02, "#b6d3cc", group);
    const screenMaterial = new THREE.MeshBasicMaterial({ color: 0xb6d3cc, transparent: true, opacity: .9 });
    deskScreens.push(screenMaterial);
    const screenGeometry = new THREE.PlaneGeometry(1.02, .61); geometries.add(screenGeometry);
    const screenMesh = new THREE.Mesh(screenGeometry, screenMaterial);
    screenMesh.position.set(0, 1.58, -.151); group.add(screenMesh);
    box(-.29, 1.57, -.147, .3, .38, .012, color, group);
    for (let i = 0; i < 4; i++) box(.18, 1.78 - i * .13, -.145, .47 - i % 2 * .12, .035, .012, "#f0f4de", group);
    box(0, 1.19, -.22, .07, .2, .07, "#354c48", group); box(0, 1.1, -.22, .48, .03, .28, "#354c48", group);
    box(-.07, 1.11, .29, .72, .025, .25, "#596e67", group);
    cylinder(.89, 1.2, .27, .1, .24, "#f6f0de", group); cylinder(.89, 1.33, .27, .075, .007, "#594237", group);
    box(-.95, 1.12, .13, .35, .045, .45, color, group);
    chair(x, z + (reverse ? -1 : 1), reverse ? Math.PI : 0);
  }
  // Every workstation lives inside its own glass room on floor 1.
  desk(-9, -5, "#4f9383"); desk(-6.5, -5, "#9880bd");        // Ruang kiri: produksi & QC
  desk(-9, -2.8, "#7c9b5b", true); desk(-6.5, -2.8, "#697db8", true); // aset & Facebook
  desk(.5, -5, "#c99433");                                   // Ruang creative: Pimpinan
  desk(6.5, -5, "#588db7"); desk(9, -5, "#c28d54");          // Distribusi & pemulihan
  // Storage and open shelving along the social studio.
  box(-11.3, .72, -4.4, .8, 1.4, 3.2, "#c5a17b");
  for (let i = 0; i < 5; i++) box(-10.87, .8, -5.6 + i * .55, .04, .92, .035, "#9e805e");
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
  // Ground floor only: all work and movement happens on this single level.
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
  for (const x of [-8, 0, 8]) pendant(x, -4);
  for (const x of [-7.5, 7.5]) pendant(x, 4.2);
  // Six articulated colleagues with tailored silhouettes, faces, badges and
  // role details. Every part is local geometry; no external model or texture.
  const people = OFFICE_PEOPLE.map((person, index) => {
    const group = new THREE.Group(); scene.add(group);
    const body = new THREE.Group(); group.add(body);
    const lead = person.id === 'director';
    const skin = ["#d9a57f", "#bd8b69", "#e3ba94", "#c99570"][index % 4];
    const hairTone = ["#3c342c", "#54402f", "#2f2b29", "#6a4f37"][index % 4];
    // Tailored torso, shoulder line, lanyard and a small visible work badge.
    box(0, .92, 0, .42, .54, .26, person.color, body);
    box(0, 1.13, .005, .5, .13, .3, person.color, body);
    box(0, 1.13, .16, .17, .07, .02, "#f5eedc", body);
    box(.02, .97, .155, .026, .27, .016, lead ? "#d8a82f" : "#dbe5d2", body);
    box(.1, .85, .17, .13, .11, .016, "#fffaf0", body);
    if (lead) box(0, 1.04, .165, .06, .3, .012, "#d8a82f", body);
    // Head pivot keeps face, hair and accessories together during head turns.
    const head = new THREE.Group(); head.position.set(0, 1.44, 0); body.add(head);
    sphere(0, .02, 0, .215, skin, head).scale.y = 1.12;
    const cap = sphere(0, .14, -.025, .225, hairTone, head); cap.scale.set(1.02, .58, 1.04);
    if (index % 3 === 0) { const bun = sphere(0, .2, -.19, .105, hairTone, head); bun.scale.set(1, .85, 1); }
    else if (index % 3 === 1) box(-.11, .1, -.16, .2, .16, .12, hairTone, head);
    else box(0, .11, -.19, .38, .22, .1, hairTone, head);
    for (const side of [-1, 1]) {
      sphere(side * .075, .04, .192, .019, "#2c392f", head);
      box(side * .075, .087, .194, .06, .012, .008, hairTone, head);
    }
    sphere(0, -.018, .208, .016, skin, head);
    box(0, -.076, .192, .072, .009, .008, "#8c5d50", head);
    if (lead) {
      const lens = new THREE.TorusGeometry(.055, .008, 6, 14); geometries.add(lens);
      for (const side of [-1, 1]) {
        const frame = new THREE.Mesh(lens, material("#5a5340"));
        frame.position.set(side * .078, .04, .208); head.add(frame);
      }
      box(0, .04, .209, .05, .008, .008, "#5a5340", head);
    }
    if (index === 2 || index === 3) {
      const band = new THREE.TorusGeometry(.24, .018, 6, 18, Math.PI); geometries.add(band);
      const headset = new THREE.Mesh(band, material("#34463f"));
      headset.rotation.z = Math.PI; headset.position.set(0, .08, 0); head.add(headset);
      sphere(-.2, -.04, .14, .035, "#34463f", head);
    }
    const legs = [-1, 1].map(side => {
      const limb = new THREE.Group(); limb.position.set(side * .12, .67, 0); body.add(limb);
      box(0, -.24, 0, .14, .48, .16, "#465650", limb);
      box(0, -.47, .055, .19, .13, .29, "#2f3f37", limb); return limb;
    });
    const arms = [-1, 1].map(side => {
      const limb = new THREE.Group(); limb.position.set(side * .29, 1.12, 0); body.add(limb);
      box(0, -.18, 0, .13, .38, .15, person.color, limb);
      box(0, -.36, 0, .14, .07, .16, "#40514a", limb);
      sphere(0, -.42, 0, .078, skin, limb); return limb;
    });
    const mug = cylinder(.31, .76, .13, .075, .17, "#f7e8d0", body); mug.visible = false;
    const book = box(.1, .98, .3, .34, .05, .25, "#d8c9a6", body); book.visible = false;
    const mouse = cylinder(.42, 1.14, .86, .07, .04, "#d8d4c7", body); mouse.visible = false;
    // A personal workstation follows anyone who sits down: chair, desk and
    // a lit monitor, so nobody is ever seen sitting in empty space.
    const seat = new THREE.Group(); scene.add(seat);
    box(0, .62, 0, .78, .18, .74, "#4f655f", seat);
    box(0, 1.06, -.34, .8, .68, .14, "#4f655f", seat);
    const seatLegs = new THREE.Group(); seat.add(seatLegs);
    for (const dx of [-.28, .28]) for (const dz of [-.26, .26]) {
      const leg = cylinder(dx, .29, dz, .05, .58, "#485451", seatLegs);
      leg.rotation.z = dx > 0 ? -.05 : .05;
    }
    const station = new THREE.Group(); scene.add(station);
    box(0, 1.02, 1, 2.4, .14, 1.1, "#ead9b8", station);
    for (const dx of [-1.05, 1.05]) for (const dz of [.62, 1.4]) box(dx, .48, dz, .08, 1, .08, "#4e5c58", station);
    box(0, 1.3, 1.35, .08, .42, .08, "#354c48", station);
    box(0, 1.74, 1.35, 1.15, .72, .09, "#354c48", station);
    box(0, 1.74, 1.28, 1.02, .6, .02, "#b6d3cc", station);
    box(0, 1.12, .86, .72, .03, .25, "#596e67", station);
    cylinder(.86, 1.16, .86, .1, .22, "#f6f0de", station);
    const prop = new THREE.Group(); scene.add(prop);
    const notebook = box(.62, 1.12, 1.12, .62, .05, .46, "#d8c9a6", prop);
    const phone = box(.52, 1.42, 1, .24, .46, .06, "#354c48", prop);
    const copier = box(-1.1, 1.05, 1.15, 1.4, .95, 1, "#9aa9a2", prop);
    const cup = cylinder(.55, 1.16, 1.02, .11, .24, "#f7e8d0", prop);
    const cards = box(.62, 1.02, 1.16, .5, .04, .36, "#f6f0de", prop);
    // A quiet floor glow shows which colleague the real worker queue is
    // driving right now. It never changes a status or an approval.
    const glowGeometry = new THREE.CircleGeometry(.72, 28); geometries.add(glowGeometry);
    const glowMaterial = new THREE.MeshBasicMaterial({ color: person.color, transparent: true,
      opacity: 0, depthWrite: false, side: THREE.DoubleSide });
    glowMaterials.push(glowMaterial);
    const glow = new THREE.Mesh(glowGeometry, glowMaterial);
    glow.rotation.x = -Math.PI / 2; glow.visible = false; scene.add(glow);
    return { group, body, head, legs, arms, mug, book, mouse, seat, station, prop, glow, glowMaterial,
      notebook, phone, copier, cup, cards, point: { ...person.desk } as OfficePoint,
      path: [] as OfficePoint[], destination: "", pendingDestination: "", pendingSince: 0,
      speed: 0, rotation: person.desk.z > 0 ? 0 : Math.PI, greetUntil: 0 };
  });
  let width = 1, height = 1, zoom = 1, night = false;
  let lastSeconds = 0, lastStates: Record<string, string> = {}, lastWork: Record<string, OfficeWorkCue> = {};
  // When the director sees a real blocker, he walks to that department
  // instead of continuing his routine round.
  let attentionIndex: number | null = null;
  let autoTarget: { x: number; z: number; zoom: number } | null = null;
  const projected = new THREE.Vector3();
  function updateProjection() {
    const aspect = Math.max(width, 1) / Math.max(height, 1);
    const vertical = Math.max(11.6, 17.4 / aspect) / zoom;
    camera.left = -vertical * aspect; camera.right = vertical * aspect;
    camera.top = vertical; camera.bottom = -vertical; camera.updateProjectionMatrix();
  }
  function resize() {
    width = Math.max(host.clientWidth, 1); height = Math.max(host.clientHeight, 1);
    renderer.setSize(width, height);
    updateProjection();
    render(lastSeconds, night, lastStates, lastWork);
  }
  function point(x: number, y: number, z: number) {
    projected.set(x, y, z).project(camera);
    return { x: (projected.x * .5 + .5) * width, y: (-projected.y * .5 + .5) * height };
  }
  function render(seconds: number, isNight: boolean, states: Record<string, string> = {}, work: Record<string, OfficeWorkCue> = {}) {
    const delta = Math.min(Math.max(seconds - lastSeconds, 0), .12);
    lastSeconds = seconds; lastStates = states; lastWork = work;
    camera.updateMatrixWorld();
    if (night !== isNight) {
      night = isNight;
      ambient.intensity = night ? 1.05 : 2.5;
      sun.intensity = night ? .55 : 3.2;
      fill.intensity = night ? .45 : 1.4;
      for (const lamp of lamps) {
        lamp.shade.emissiveIntensity = night ? 3.2 : .04;
        lamp.light.intensity = night ? 4.2 : 0;
        lamp.pool.opacity = night ? .16 : 0;
      }
    }
    if (autoTarget && delta > 0) {
      const ease = Math.min(1, delta * 2.6);
      pan.x += (autoTarget.x - pan.x) * ease;
      pan.z += (autoTarget.z - pan.z) * ease;
      const before = zoom;
      zoom += (autoTarget.zoom - zoom) * ease;
      if (Math.abs(zoom - before) > .0005) { updateProjection(); onZoomChange?.(zoom); }
      refreshFocus();
      if (Math.abs(autoTarget.x - pan.x) < .02 && Math.abs(autoTarget.z - pan.z) < .02
          && Math.abs(autoTarget.zoom - zoom) < .02) {
        pan.x = autoTarget.x; pan.z = autoTarget.z; zoom = autoTarget.zoom;
        updateProjection(); refreshFocus(); autoTarget = null;
      }
    }
    const directorRound = directorState(seconds, attentionIndex ?? -1);
    const visit = patrolIndex(directorRound);
    const projections = people.map((person, index) => {
      const profile = OFFICE_PEOPLE[index];
      const observedState = states[profile.id] || "unavailable";
      const state = profile.id === 'director' ? directorRound : observedState;
      // Motion follows the worker's real state and stage. The staggered
      // routine is only a fallback when a department has no live work yet.
      const routine = ['desk', 'desk', 'chat', 'desk', 'notice', 'desk', 'sofa', 'desk', 'queued', 'desk', 'blocked', 'desk'];
      // Whoever the director is visiting stays at their desk, so the check-in
      // is about their real work instead of an empty chair.
      const motionState = profile.id === 'director' ? state
        : visit === index && observedState !== 'unavailable' ? 'desk'
          : (observedState === 'unavailable'
            ? observedState : officeMotionFromWork(work[profile.id], routine[(Math.floor(seconds / 55) + index) % routine.length]));
      const target = officeDestination(index, motionState);
      const destination = `${target.x}:${target.z}:${target.y ?? 0}`;
      if (state === "unavailable") {
        person.pendingDestination = ""; person.pendingSince = 0;
      } else if (destination !== person.destination && !person.path.length) {
        // A status flicker must not send someone back and forth forever.
        // The new destination has to stay put for a moment before walking.
        if (destination === person.pendingDestination) {
          person.pendingSince += delta;
          if (person.pendingSince >= 1.2) {
            person.path = Math.hypot(target.x - person.point.x, target.z - person.point.z,
              (target.y ?? 0) - (person.point.y ?? 0)) > .01 ? officePath(person.point, target) : [];
            person.destination = destination;
            person.pendingDestination = ""; person.pendingSince = 0;
          }
        } else {
          person.pendingDestination = destination; person.pendingSince = 0;
        }
      } else {
        person.pendingDestination = ""; person.pendingSince = 0;
      }
      const walking = state !== "unavailable" && person.path.length > 0;
      person.speed += ((walking ? 1 : 0) - person.speed) * Math.min(1, delta * 5);
      if (walking && delta > 0) {
        const others = people.map((other, otherIndex) => ({ otherIndex, point: other.point }))
          .filter(other => other.otherIndex !== index);
        const step = officeStep(person.point, person.path, delta * person.speed);
        const avoided = officeAvoidStep(person.point, step, step.path, others.map(other => other.point));
        person.point = { x: avoided.point.x, z: avoided.point.z, y: step.y };
        person.path = avoided.path;
        if (avoided.greeting) {
          person.greetUntil = seconds + 1.1;
          const met = others[avoided.blocker];
          if (met) people[met.otherIndex].greetUntil = seconds + 1.1;
        }
        let turn = step.rotation - person.rotation;
        turn = Math.atan2(Math.sin(turn), Math.cos(turn));
        person.rotation += turn * Math.min(1, delta * 8);
      }
      if (!person.path.length) {
        const partner = officeDestination(index % 2 ? index - 1 : Math.min(index + 1, OFFICE_PEOPLE.length - 1), 'chat');
        const desired = target.activity === "chat" ? Math.atan2(partner.x - person.point.x, partner.z - person.point.z)
          : target.activity === "desk" ? (profile.desk.z > 0 ? 0 : Math.PI)
            : target.activity === "patrol" && visit >= 0
              ? Math.atan2(OFFICE_PEOPLE[visit].desk.x - person.point.x, OFFICE_PEOPLE[visit].desk.z - person.point.z)
            : target.activity === "observing" || target.activity === "reading" || target.activity === "sofa" ? Math.PI
              : target.activity === "meeting" ? -Math.PI / 2
                : target.activity === "briefing" || target.activity === "call"
                  ? Math.atan2(-8 - person.point.x, 2 - person.point.z) : 0;
        let turn = desired - person.rotation;
        turn = Math.atan2(Math.sin(turn), Math.cos(turn));
        person.rotation += turn * Math.min(1, delta * 5);
      }
      const activity = person.greetUntil > seconds ? "greet" as const
        : person.path.length && state !== "unavailable" ? "walk" as const : target.activity;
      const pose = { ...person.point, rotation: person.rotation, activity };
      person.group.position.set(pose.x, pose.y ?? 0, pose.z);
      const glowState = profile.id === 'director'
        ? (attentionIndex === null ? 'idle' : 'running') : (work[profile.id]?.state || observedState);
      person.glowMaterial.color.set(glowState === 'blocked' ? '#c98a35' : glowState === 'queued' ? '#6d8fb8' : profile.color);
      person.glowMaterial.opacity = glowState === 'running' ? .16 + Math.sin(seconds * 2 + index) * .03
        : glowState === 'blocked' ? .13 : glowState === 'queued' ? .07 : 0;
      person.glow.visible = person.glowMaterial.opacity > .01;
      person.glow.position.set(pose.x, .014 + (pose.y ?? 0), pose.z);
      person.group.rotation.y = pose.rotation + (pose.activity === 'observing' ? Math.sin(seconds * .8) * .5 : 0);
      person.head.rotation.y = Math.sin(seconds * .6 + index) * .16;
      person.mouse.visible = pose.activity === 'desk' || pose.activity === 'observing';
      person.mouse.position.x = .42 + Math.sin(seconds * 1.8 + index) * .08;
      for (const material of deskScreens) material.opacity = .84 + Math.sin(seconds * .9) * .12;
      const seated = ["desk", "observing", "reading", "cards", "write", "snack"].includes(pose.activity);
      person.seat.visible = seated;
      person.seat.position.set(pose.x, pose.y ?? 0, pose.z);
      person.seat.rotation.y = pose.rotation;
      const workstation = pose.activity === "reading";
      person.station.visible = workstation;
      person.station.position.set(pose.x, pose.y ?? 0, pose.z);
      person.station.rotation.y = pose.rotation;
      const propKind = pose.activity;
      person.prop.visible = ["write", "cards", "copy", "call", "snack", "notice"].includes(propKind);
      person.prop.position.set(pose.x, pose.y ?? 0, pose.z);
      person.prop.rotation.y = pose.rotation;
      person.notebook.visible = propKind === "write" || propKind === "cards" || propKind === "notice";
      person.cards.visible = propKind === "cards";
      person.phone.visible = propKind === "call";
      person.copier.visible = propKind === "copy";
      person.cup.visible = propKind === "snack";
      const quiet = Math.sin(seconds * 1.4 + index) * .03;
      person.body.position.y = pose.activity === "walk" ? Math.abs(Math.sin(seconds * 8)) * .045
        : pose.activity === "sofa" ? -.3
          : pose.activity === "meeting" ? -.16
            : pose.activity === "desk" ? -.12
              : pose.activity === "coffee" || pose.activity === "reading" || pose.activity === "greet" ? quiet : 0;
      person.legs.forEach((leg, side) => leg.rotation.x = pose.activity === "walk"
        ? Math.sin(seconds * 8 + side * Math.PI) * .52
        : pose.activity === "meeting" || pose.activity === "desk" ? -.95 : 0);
      person.arms.forEach((arm, side) => {
        arm.rotation.z = 0;
        switch (pose.activity) {
          case "greet": arm.rotation.x = side ? -1 + Math.sin(seconds * 7) * .16 : -.2;
            arm.rotation.z = side ? -.28 : 0; break;
          case "walk": arm.rotation.x = Math.sin(seconds * 8 + side * Math.PI + Math.PI) * .4; break;
          case "meeting": arm.rotation.x = -.5 + Math.sin(seconds * 2.5 + side) * .25; break;
          case "desk": arm.rotation.x = state === "running" ? -.55 + Math.sin(seconds * 5 + side) * .08 : -.2; break;
          case "coffee": arm.rotation.x = side ? -.78 + Math.sin(seconds * 1.6) * .1 : -.18; break;
          case "reading": arm.rotation.x = -.72 + side * .04; break;
          case "observing": arm.rotation.x = -.18 + Math.sin(seconds * .8 + side) * .06; break;
          case "notice": arm.rotation.x = side ? -.58 + Math.sin(seconds * 2 + side) * .12 : -.18; break;
          case "chat": arm.rotation.x = side ? -.45 + Math.sin(seconds * 2.6 + side) * .18 : -.15; break;
          case "patrol": arm.rotation.x = side ? -.58 + Math.sin(seconds * 1.3) * .07 : -.16; break;
          case "briefing": arm.rotation.x = side ? -.7 + Math.sin(seconds * 2.4 + side) * .22 : -.3; break;
          case "lounge": case "sofa": arm.rotation.x = side ? -.42 + quiet * 2 : -.14; break;
          case "write": case "cards": case "copy": case "call": case "snack":
            arm.rotation.x = side ? -.72 + Math.sin(seconds * 2 + side) * .06 : -.4; break;
          default: arm.rotation.x = -.2;
        }
      });
      person.mug.visible = pose.activity === "coffee";
      person.book.visible = pose.activity === "reading";
      return { id: OFFICE_PEOPLE[index].id, ...point(pose.x, 2.15 + (pose.y ?? 0), pose.z), activity: pose.activity, chatWith: undefined as string | undefined };
    });
    // Only surface the chat bubble once the director actually reaches the
    // colleague, never while he is still crossing the floor.
    if (visit >= 0) {
      const directorPoint = people[people.length - 1].point;
      const colleaguePoint = people[visit].point;
      if (Math.hypot(directorPoint.x - colleaguePoint.x, directorPoint.z - colleaguePoint.z) < 2.2) {
        const lead = projections.find(row => row.id === 'director');
        const colleague = projections.find(row => row.id === OFFICE_PEOPLE[visit].id);
        if (lead) lead.chatWith = OFFICE_PEOPLE[visit].id;
        if (colleague) colleague.chatWith = 'director';
      }
    }
    renderer.render(scene, camera);
    project(projections, OFFICE_AREAS.map(area => ({ id: area.id, ...point(area.x, .25 + area.y, area.z), activity: "desk" })));
  }
  let dragging = false, dragX = 0, dragY = 0;
  const canvas = renderer.domElement;
  canvas.style.cursor = "grab";
  canvas.style.touchAction = "none";
  canvas.addEventListener("pointerdown", event => {
    dragging = true; dragX = event.clientX; dragY = event.clientY; autoTarget = null;
    canvas.setPointerCapture(event.pointerId); canvas.style.cursor = "grabbing";
  });
  canvas.addEventListener("pointermove", event => {
    if (!dragging) return;
    const dx = event.clientX - dragX, dy = event.clientY - dragY;
    if (event.shiftKey || event.buttons === 2) {
      const step = 12 / Math.max(.6, zoom);
      pan.x -= dx * step / Math.max(width, 1);
      pan.z -= dy * step / Math.max(height, 1);
      pan.x = Math.max(-6, Math.min(6, pan.x));
      pan.z = Math.max(-5, Math.min(5, pan.z));
      refreshFocus();
    } else {
      azimuth += dx * .007;
      elevation = Math.min(1.32, Math.max(.12, elevation - dy * .005));
      updateCamera();
    }
    dragX = event.clientX; dragY = event.clientY;
    render(lastSeconds, night, lastStates, lastWork);
  });
  canvas.addEventListener("contextmenu", event => event.preventDefault());
  const endDrag = () => { dragging = false; canvas.style.cursor = "grab"; };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", endDrag);
  canvas.addEventListener("wheel", event => {
    event.preventDefault();
    autoTarget = null;
    zoom = Math.min(2.6, Math.max(.6, zoom * (event.deltaY > 0 ? .9 : 1.1)));
    onZoomChange?.(zoom); refreshFocus(); resize();
  }, { passive: false });
  const observer = new ResizeObserver(resize); observer.observe(host); resize();
  return {
    render,
    zoom(value: number) { zoom = value; onZoomChange?.(zoom); refreshFocus(); resize(); },
    rotate(delta: number) { azimuth += delta; updateCamera(); render(lastSeconds, night, lastStates, lastWork); },
    tilt(delta: number) { elevation = Math.min(1.32, Math.max(.12, elevation + delta));
      updateCamera(); render(lastSeconds, night, lastStates, lastWork); },
    focusOn(id: string) {
      const index = OFFICE_PEOPLE.findIndex(row => row.id === id);
      if (index < 0) return;
      pan.set(people[index].point.x, 0, people[index].point.z);
      refreshFocus(); render(lastSeconds, night, lastStates, lastWork);
    },
    setAttention(index: number | null) {
      attentionIndex = index !== null && index >= 0 && index < OFFICE_PEOPLE.length - 1
        && OFFICE_PEOPLE[index].id !== 'director' ? index : null;
      render(lastSeconds, night, lastStates, lastWork);
    },
    autoFocus(index: number | null, level = 1.45) {
      const safe = index !== null && index >= 0 && index < OFFICE_PEOPLE.length ? index : null;
      autoTarget = safe === null ? { x: 0, z: 0, zoom: 1 }
        : { x: people[safe].point.x, z: people[safe].point.z, zoom: level };
    },
    cancelAutoFocus() { autoTarget = null; },
    resetView() { azimuth = BASE_AZIMUTH; elevation = BASE_ELEVATION; zoom = 1; pan.set(0, 0, 0); autoTarget = null;
      onZoomChange?.(zoom); refreshFocus(); resize(); },
    dispose() {
      observer.disconnect(); geometries.forEach(geometry => geometry.dispose());
      materials.forEach(mat => mat.dispose()); signMaterials.forEach(mat => mat.dispose());
      lampMaterials.forEach(mat => mat.dispose()); poolMaterials.forEach(mat => mat.dispose());
      glowMaterials.forEach(mat => mat.dispose());
      deskScreens.forEach(material => material.dispose());
      textures.forEach(texture => texture.dispose());
      renderer.dispose(); renderer.domElement.remove();
    },
  };
}
