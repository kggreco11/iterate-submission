import * as THREE from 'three';
import { OrbitControls } from 'three/controls';
import { mergeGeometries } from 'three/geometry';

const DATA = JSON.parse(document.getElementById('run-data').textContent);
const R = DATA.replay, T = R.trace, $ = id => document.getElementById(id);
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const money = v => '$' + (v / 1e6).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + 'M';
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let index = T.length - 1, selected = '', playing = false, timer, showConnections = false;
const renderer = new THREE.WebGLRenderer({ canvas: $('scene'), antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.25;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#dfe5de');
scene.fog = new THREE.Fog('#dfe5de', 450, 950);
const camera = new THREE.PerspectiveCamera(37, 1, .1, 700);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = !reduced;
controls.dampingFactor = .09;
controls.maxPolarAngle = Math.PI * .485;
controls.minDistance = 12;
controls.maxDistance = 600;
scene.add(new THREE.HemisphereLight('#f8fbff', '#8f9580', 2.5));
const sun = new THREE.DirectionalLight('#fff1d7', 3.2);
sun.position.set(-65, 105, 45);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -135, right: 135, top: 100, bottom: -100, near: 1, far: 280 });
sun.shadow.normalBias = .12;
scene.add(sun);

const material = (color, metalness = 0, roughness = .75) => new THREE.MeshStandardMaterial({ color, metalness, roughness });
const M = {
  earth: material('#aeb6a4'), concrete: material('#c5c7bb'), pad: material('#d9d9cc'),
  road: material('#737b74'), marking: material('#e5dfbd'), steel: material('#abb9ba', .65, .33),
  white: material('#dce0d9', .25, .55), dark: material('#53686b', .55, .5),
  structure: material('#637a7a', .65, .4), rail: material('#cca553', .45, .48),
  green: material('#46816c', .35, .5), blue: material('#527e8c', .4, .45),
  amber: material('#d99a4b', .5, .38), pipe: material('#b9c3ba', .65, .4),
  roof: material('#8f9f91'), window: material('#47636b', .55, .25), rubber: material('#343d38'),
};
const unitBox = new THREE.BoxGeometry(1, 1, 1);
const unitCylinder = new THREE.CylinderGeometry(1, 1, 1, 16);
const unitSphere = new THREE.SphereGeometry(1, 16, 10);
function mesh(group, geometry, mat, position, scale = [1, 1, 1], rotation) {
  const object = new THREE.Mesh(geometry, mat);
  object.position.set(...position); object.scale.set(...scale);
  if (rotation) object.rotation.set(...rotation);
  object.castShadow = true; object.receiveShadow = true;
  group.add(object); return object;
}
const box = (g, pos, size, mat) => mesh(g, unitBox, mat, pos, size);
const cyl = (g, pos, radius, height, mat) => mesh(g, unitCylinder, mat, pos, [radius, height, radius]);
function beam(g, a, b, radius, mat) {
  const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b), d = end.clone().sub(start);
  const m = mesh(g, unitCylinder, mat, start.clone().add(end).multiplyScalar(.5).toArray(), [radius, d.length(), radius]);
  m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()); return m;
}
function pipe(g, points, radius = .12, mat = M.pipe) {
  points.slice(1).forEach((p, i) => beam(g, points[i], p, radius, mat));
  points.slice(1, -1).forEach(p => mesh(g, unitSphere, mat, p, [radius, radius, radius]));
}
function horizontalVessel(g, x, y, z, length, radius, mat = M.steel) {
  mesh(g, unitCylinder, mat, [x, y, z], [radius, length, radius], [0, 0, Math.PI / 2]);
  for (const sign of [-1, 1]) {
    mesh(g, unitSphere, mat, [x + sign * length / 2, y, z], [radius * .48, radius, radius]);
    box(g, [x + sign * length * .3, y / 2, z], [.3, y, radius * 1.4], M.dark);
  }
}
function ring(g, x, y, z, radius, mat, tube = .045) {
  const geometry = new THREE.TorusGeometry(radius, tube, 5, 24);
  const m = mesh(g, geometry, mat, [x, y, z], [1, 1, 1], [Math.PI / 2, 0, 0]);
  m.userData.ownGeometry = true;
}
// Merge surfaces per material to keep the detailed assemblies inexpensive to render.
function bake(group) {
  group.updateMatrixWorld(true);
  const buckets = new Map();
  group.traverse(object => {
    if (!object.isMesh) return;
    const geometry = object.geometry.clone().applyMatrix4(object.matrixWorld);
    geometry.deleteAttribute('uv');
    const entries = buckets.get(object.material) || [];
    entries.push(geometry); buckets.set(object.material, entries);
    if (object.userData.ownGeometry) object.geometry.dispose();
  });
  const result = new THREE.Group();
  for (const [mat, entries] of buckets) {
    const combined = mergeGeometries(entries, false);
    const object = new THREE.Mesh(combined, mat);
    object.castShadow = true; object.receiveShadow = true; result.add(object);
    entries.forEach(g => g.dispose());
  }
  return result;
}
function removeGroup(group) {
  group.traverse(o => { if (o.isMesh) o.geometry.dispose(); });
  scene.remove(group);
}
const labels = [];
function label(text, position) {
  const e = document.createElement('div'); e.className = 'site-label'; e.textContent = text;
  $('labels').append(e); labels.push({ e, p: new THREE.Vector3(...position) });
}

// Four fixed equipment rows, grouped by process-tree order rather than drawn as a tree.
const allColumns = [...new Set(T.flatMap(t => Object.keys(t.columns)))].sort();
const positions = {};
const bays = Math.max(1, Math.ceil(allColumns.length / 4));
const bayStep = 11, halfWidth = Math.max(50, (bays - 1) * bayStep / 2 + 8);
allColumns.forEach((p, i) => {
  const row = Math.floor(i / bays), bay = i % bays;
  positions[p] = { x: (bay - (bays - 1) / 2) * bayStep, z: [-26, -11, 11, 26][row], row, bay, tag: `C-${String(i + 101)}` };
});
const components = R.components;
const storageX = halfWidth + 26;
const tankPositions = new Map(components.map((name, i) => [name, { x: storageX + (i % 3) * 9, z: (Math.floor(i / 3) - 1.5) * 14 }]));
const site = new THREE.Group();
box(site, [13, -.7, 0], [halfWidth * 2 + 110, 1.3, 111], M.earth);
box(site, [7, -.09, 0], [halfWidth * 2 + 86, .16, 98], M.concrete);
// Perimeter service roads and a clear cross-site corridor.
for (const z of [-43, 43]) {
  box(site, [9, .03, z], [halfWidth * 2 + 87, .08, 7], M.road);
  for (let x = -halfWidth - 33; x < halfWidth + 49; x += 8) box(site, [x, .08, z], [3, .015, .12], M.marking);
}
for (const x of [-halfWidth - 12, halfWidth + 10]) {
  box(site, [x, .03, 0], [6, .08, 80], M.road);
  for (let z = -35; z <= 35; z += 8) box(site, [x, .08, z], [.12, .015, 3], M.marking);
}
for (const z of [-26, -11, 11, 26]) box(site, [0, .12, z], [halfWidth * 2, .24, 11.5], M.pad);
// Central rack: two levels, regular steel portals and overhead utility lines.
for (let x = -halfWidth; x <= halfWidth + 4; x += 9) {
  for (const z of [-3, 3]) { box(site, [x, 3.2, z], [.24, 6.4, .24], M.structure); box(site, [x, .25, z], [1, .5, 1], M.pad); }
  for (const y of [4.3, 6.4]) box(site, [x, y, 0], [.3, .3, 6.6], M.structure);
  if (Math.round(x) % 3 === 0) beam(site, [x, .4, -3], [x + 8.8, 6.4, -3], .07, M.structure);
}
for (const z of [-3, 3]) box(site, [0, 6.4, z], [halfWidth * 2, .2, .2], M.structure);
for (let i = 0; i < 9; i++) pipe(site, [[-halfWidth - 7, 6.7, -2.5 + i * .62], [halfWidth + 20, 6.7, -2.5 + i * .62]], i % 3 ? .11 : .2, i === 2 ? M.blue : M.pipe);
for (let x = -halfWidth + 6; x < halfWidth; x += bayStep) {
  for (const sign of [-1, 1]) {
    for (const z of [8 * sign, 21 * sign]) {
      for (const dx of [-.8, .8]) box(site, [x + dx, 2.2, z], [.14, 4.4, .14], M.structure);
      box(site, [x, 4.4, z], [2, .18, .18], M.structure);
    }
    for (let lane = 0; lane < 3; lane++) pipe(site, [[x + lane * .4, 6.7, sign * 2.6], [x + lane * .4, 4.6, sign * 5], [x + lane * .4, 4.6, sign * 31]], .095);
  }
}
// Tank containment walls and feed reception.
function bund(cx, cz, width, depth) {
  box(site, [cx, .16, cz], [width, .3, depth], M.pad);
  for (const z of [cz - depth / 2, cz + depth / 2]) box(site, [cx, .65, z], [width, 1.3, .3], M.concrete);
  for (const x of [cx - width / 2, cx + width / 2]) box(site, [x, .65, cz], [.3, 1.3, depth], M.concrete);
}
bund(storageX + 9, 0, 30, 59);
bund(-halfWidth - 29, -16, 22, 32);
function storageTank(g, x, z, r, h, mat) {
  cyl(g, [x, .3, z], r + .4, .6, M.concrete);
  cyl(g, [x, h / 2 + .6, z], r, h, mat);
  mesh(g, new THREE.ConeGeometry(r, .9, 24), M.white, [x, h + 1, z]).userData.ownGeometry = true;
  ring(g, x, h + .9, z, r * .95, M.rail);
  for (let a = 0; a < Math.PI * 2; a += Math.PI / 8) beam(g, [x + Math.cos(a) * r * .95, h + .5, z + Math.sin(a) * r * .95], [x + Math.cos(a) * r * .95, h + 1.1, z + Math.sin(a) * r * .95], .035, M.rail);
  for (const dx of [-.25, .25]) beam(g, [x + dx, .5, z + r + .1], [x + dx, h + .8, z + r + .1], .04, M.dark);
  for (let y = .7; y < h + .8; y += .38) beam(g, [x - .25, y, z + r + .1], [x + .25, y, z + r + .1], .03, M.dark);
}
for (const z of [-23, -9]) storageTank(site, -halfWidth - 29, z, 4.5, 7.3, M.white);
pipe(site, [[-halfWidth - 24, 1, -9], [-halfWidth - 18, 1, -9], [-halfWidth - 18, 6.7, 0], [-halfWidth, 6.7, 0]], .22);
// Control room, electrical services and cooling equipment occupy the service edge.
box(site, [-halfWidth - 29, 2, 21], [18, 4, 12], M.white);
box(site, [-halfWidth - 29, 4.2, 21], [19, .5, 13], M.roof);
for (let x = -halfWidth - 36; x <= -halfWidth - 22; x += 3) box(site, [x, 2.4, 27.03], [1.9, 1.3, .08], M.window);
box(site, [-halfWidth - 29, 1.4, 27.08], [1.3, 2.7, .09], M.dark);
for (const x of [-halfWidth - 34, -halfWidth - 26]) box(site, [x, 4.7, 21], [3, .6, 2], M.dark);
for (let i = 0; i < 4; i++) {
  const x = -22 + i * 11;
  box(site, [x, 1, -36], [8, 1.5, 4], M.structure);
  for (const dx of [-2, 2]) { cyl(site, [x + dx, 1.95, -36], 1.5, .45, M.white); cyl(site, [x + dx, 2.2, -36], 1.2, .08, M.dark); }
}
// A small service vehicle gives the assembly a familiar sense of scale.
box(site, [-halfWidth - 29, .9, 34], [4.4, 1.2, 1.9], M.white);
box(site, [-halfWidth - 30, 1.8, 34], [1.7, 1, 1.8], M.white);
box(site, [-halfWidth - 30.9, 1.85, 34], [.04, .55, 1.4], M.window);
for (const dx of [-1.4, 1.4]) for (const dz of [-1, 1]) mesh(site, unitCylinder, M.rubber, [-halfWidth - 29 + dx, .55, 34 + dz], [.43, .2, .43], [Math.PI / 2, 0, 0]);
// Low perimeter fence.
for (const z of [-49, 49]) {
  for (let x = -halfWidth - 43; x < halfWidth + 65; x += 6) beam(site, [x, 0, z], [x, 2, z], .045, M.dark);
  for (const y of [.7, 1.8]) beam(site, [-halfWidth - 43, y, z], [halfWidth + 62, y, z], .025, M.dark);
}
scene.add(bake(site));
label('FEED RECEPTION', [-halfWidth - 29, .3, -35]);
label('CONTROL & SERVICES', [-halfWidth - 29, .3, 31]);
label('PRODUCT STORAGE', [storageX + 9, .3, 34]);
label('COMMON PIPE RACK', [0, 7, 0]);
label('SEPARATION TRAINS', [0, .3, -33]);

function columnAssembly(settings, changed) {
  const g = new THREE.Group(), shell = changed ? M.amber : M.steel;
  const height = 6 + Math.sqrt(settings.n_stages) * 1.15;
  const radius = .78;
  box(g, [0, .3, 0], [3.3, .6, 3.3], M.concrete);
  cyl(g, [0, 1.15, 0], radius * 1.02, 1.7, M.dark);
  cyl(g, [0, (height + 2) / 2, 0], radius, height - 2, shell);
  mesh(g, unitSphere, shell, [0, height, 0], [radius, .55, radius]);
  mesh(g, unitSphere, shell, [0, 2, 0], [radius, .5, radius]);
  // Insulation seams, maintenance decks, guardrails and a caged ladder.
  for (let y = 3; y < height; y += 2.2) ring(g, 0, y, 0, radius + .025, M.dark, .022);
  for (const y of [height * .42, height * .72, height - .35]) {
    cyl(g, [0, y, 0], 1.3, .09, M.structure);
    ring(g, 0, y + .85, 0, 1.3, M.rail);
    ring(g, 0, y + .42, 0, 1.3, M.rail, .03);
    for (let a = 0; a < Math.PI * 2; a += Math.PI / 4) beam(g, [Math.cos(a) * 1.3, y, Math.sin(a) * 1.3], [Math.cos(a) * 1.3, y + .85, Math.sin(a) * 1.3], .035, M.rail);
  }
  for (const x of [-.25, .25]) beam(g, [x, .6, 1.04], [x, height + .5, 1.04], .04, M.dark);
  for (let y = .8; y < height + .5; y += .4) beam(g, [-.25, y, 1.04], [.25, y, 1.04], .027, M.dark);
  for (let y = 3; y < height; y += 2) ring(g, 0, y, 1.16, .45, M.dark, .025);
  // Reboiler, reflux drum, pumps and local overhead line: illustrative ancillaries.
  horizontalVessel(g, 3, 1.5, 1.4, 2.5, .48);
  horizontalVessel(g, 3, 3, -1.4, 2.7, .48);
  box(g, [3, .25, 0], [5.7, .5, 5], M.concrete);
  for (const z of [-.65, .65]) {
    box(g, [5, .6, z], [1.4, .3, .65], M.dark);
    horizontalVessel(g, 5, 1, z, .7, .25, M.blue);
  }
  pipe(g, [[0, height, 0], [0, height + 1, 0], [2, height + 1, 0], [2, 3, -1.4], [3, 3, -1.4]], .13);
  pipe(g, [[.8, 2.5, 0], [1.5, 2.5, 0], [1.5, 1.5, 1.4], [3, 1.5, 1.4]], .15);
  pipe(g, [[3, 3, -1.4], [4.7, 3, -1.4], [4.7, 1, -.65]], .09);
  return { object: bake(g), height };
}
let equipmentGroup = new THREE.Group(), connectionGroup = new THREE.Group();
scene.add(equipmentGroup, connectionGroup);
let currentNodes = [], growth = [], growthStart = 0;
const selectionLabel = document.createElement('div');
selectionLabel.className = 'site-label'; selectionLabel.id = 'selection-label'; $('labels').append(selectionLabel);
const selectionRing = new THREE.Mesh(new THREE.TorusGeometry(2.2, .09, 6, 48), M.amber);
selectionRing.rotation.x = Math.PI / 2; scene.add(selectionRing);
function buildSnapshot(t, previous, animate) {
  removeGroup(equipmentGroup); equipmentGroup = new THREE.Group(); scene.add(equipmentGroup);
  currentNodes = []; growth = [];
  for (const [p, settings] of Object.entries(t.columns)) {
    const pos = positions[p], changed = !same(settings, previous.columns[p]);
    const assembly = columnAssembly(settings, changed);
    assembly.object.position.set(pos.x, .22, pos.z);
    assembly.object.userData.path = p;
    equipmentGroup.add(assembly.object);
    const n = { p, settings, ...pos, changed, height: assembly.height, object: assembly.object };
    currentNodes.push(n);
    if (animate && !previous.columns[p]) { assembly.object.scale.y = .02; growth.push(assembly.object); }
    // Tie-ins enter the shared rack from the dedicated equipment bay.
    const tie = new THREE.Group(), sign = Math.sign(pos.z);
    pipe(tie, [[pos.x + 3, 1.5, pos.z + 1.4], [pos.x + 6, 1.5, pos.z + 1.4], [pos.x + 6, 4.6, pos.z + 1.4], [pos.x + 6, 4.6, sign * 4]], .11);
    equipmentGroup.add(bake(tie));
  }
  for (const [name, pos] of tankPositions) {
    const products = t.products.filter(p => p.component === name && p.value > 0);
    if (!products.length) continue;
    const tank = new THREE.Group();
    const lightProduct = /ethane|propane|butane/i.test(name);
    if (lightProduct) {
      // Illustrative pressure-vessel storage for the light fractions.
      box(tank, [0, .2, 0], [7.5, .4, 8], M.concrete);
      for (const z of [-2.3, 0, 2.3]) {
        horizontalVessel(tank, 0, 2.2, z, 5.5, .85, M.white);
        pipe(tank, [[-3, 2.2, z], [-3.7, 2.2, z], [-3.7, 1, 3.7]], .12, M.green);
      }
    } else {
      storageTank(tank, 0, 0, 3.15, 5.5, M.white);
      // Green band identifies product-bearing storage without inventing volume levels.
      cyl(tank, [0, 4.6, 0], 3.17, .6, M.green);
    }
    const object = bake(tank); object.position.set(pos.x, .2, pos.z); object.userData.path = 'product:' + name; equipmentGroup.add(object);
    currentNodes.push({ p: 'product:' + name, product: true, name, products, ...pos, height: 6.6, object });
  }
  growthStart = performance.now();
}
function refreshConnections() {
  removeGroup(connectionGroup); connectionGroup = new THREE.Group(); scene.add(connectionGroup);
  if (!showConnections) return;
  const n = currentNodes.find(n => n.p === selected);
  if (!n || n.product) return;
  const t = T[index];
  for (const suffix of ['T', 'B']) {
    const path = n.p + suffix;
    let destination = currentNodes.find(n => n.p === path);
    if (!destination) {
      const product = t.products.find(p => p.node === path);
      destination = currentNodes.find(n => n.product && n.name === product?.component);
    }
    if (!destination) continue;
    const lane = suffix === 'T' ? -1 : 1;
    const route = new THREE.Group();
    pipe(route, [[n.x, n.height + 1, n.z], [n.x + 2, n.height + 1, n.z], [n.x + 2, 7.5, n.z], [n.x + 2, 7.5, lane], [destination.x + 2, 7.5, lane], [destination.x + 2, 7.5, destination.z], [destination.x, 2, destination.z]], .19, suffix === 'T' ? M.green : M.amber);
    connectionGroup.add(bake(route));
  }
}
function inspect() {
  let n = currentNodes.find(n => n.p === selected);
  if (!n) n = currentNodes.find(n => n.changed) || currentNodes[0];
  selected = n?.p ?? ''; $('equipment').value = selected;
  $('focus').disabled = !n; $('connections').disabled = !n || n.product;
  selectionRing.visible = !!n; selectionLabel.style.display = n ? 'block' : 'none';
  if (!n) { $('detail').textContent = 'No separation equipment yet.\nFeed reception and site infrastructure\nare illustrative context.'; refreshConnections(); return; }
  selectionRing.position.set(n.x, .7, n.z);
  selectionLabel.textContent = n.product ? n.name : `${n.tag} / ${n.p || 'FEED'}`;
  if (n.product) {
    const value = n.products.reduce((s, p) => s + p.value, 0), flow = n.products.reduce((s, p) => s + p.flow_mol_s, 0);
    $('detail').textContent = `${n.name.toUpperCase()}\n${n.products.length} saleable outlet(s) collected\nFlow       ${flow.toFixed(2)} mol/s\nValue      ${money(value)}/yr\n\nStorage shape is illustrative;\nno inventory volume was recorded.`;
  } else {
    $('detail').textContent = `${n.tag} · PATH ${n.p || 'FEED'}\nStages         ${n.settings.n_stages}\nReflux ratio   ${n.settings.reflux}\nReboil ratio   ${n.settings.reboil}\nPressure drop  ${n.settings.dp}\n\n${n.changed ? 'Updated in this improvement' : 'Unchanged in this improvement'}\nBay ${n.bay + 1} · Equipment row ${n.row + 1}`;
  }
  refreshConnections();
}
function chart() {
  const svg = $('chart'), width = 900, max = Math.max(1, ...T.map(t => t.revenue - t.tac));
  svg.setAttribute('viewBox', '0 0 900 42'); svg.replaceChildren();
  const x = t => 3 + t.solves / Math.max(1, R.budget) * 894, y = t => 38 - (t.revenue - t.tac) / max * 32;
  function add(tag, attrs) { const el = document.createElementNS('http://www.w3.org/2000/svg', tag); for (const k in attrs) el.setAttribute(k, attrs[k]); svg.append(el); }
  const path = list => list.map((t, i) => (i ? 'L' : 'M') + x(t) + ',' + y(t)).join(' ');
  add('path', { d: path(T), fill: 'none', stroke: '#c3cec3', 'stroke-width': 2 });
  add('path', { d: path(T.slice(0, index + 1)), fill: 'none', stroke: '#275c49', 'stroke-width': 2 });
  add('circle', { cx: x(T[index]), cy: y(T[index]), r: 3, fill: '#bc742e' });
}
function show(i, animate = true) {
  index = Math.max(0, Math.min(T.length - 1, i));
  const t = T[index], previous = T[Math.max(0, index - 1)];
  buildSnapshot(t, previous, animate && !reduced);
  $('timeline').value = index;
  $('phase').textContent = index === 0 ? 'A site, ready for a process.' : index === T.length - 1 ? 'From process to plant.' : 'The separation trains take shape.';
  const columns = currentNodes.filter(n => !n.product), added = columns.filter(n => !previous.columns[n.p]).length, changed = columns.filter(n => n.changed).length;
  $('assembly-count').textContent = `${columns.length} COLUMNS / ${currentNodes.filter(n => n.product).length} PRODUCT GROUPS`;
  $('delta').textContent = index ? `${added} added · ${changed - added} retuned · +${money((t.revenue - t.tac) - (previous.revenue - previous.tac))}/yr` : 'Feed only · no installed columns';
  $('position').textContent = `${String(index + 1).padStart(2, '0')} / ${T.length} snapshots`;
  $('objective').textContent = money(t.revenue - t.tac);
  $('calls').textContent = `${t.solves} / ${R.budget} simulator calls`;
  $('elapsed').textContent = `${(t.wall_s / 60).toFixed(1)} min into recorded run`;
  $('stats').innerHTML = [['Columns', columns.length], ['Saleable outlets', t.products.filter(p => p.value > 0).length], ['Revenue / yr', money(t.revenue)], ['Cost / yr', money(t.tac)]].map(([a,b]) => `<div><small>${a}</small><b>${b}</b></div>`).join('');
  const turn = DATA.turns.find(tn => tn.valid && tn.solves_used === t.solves);
  $('note').textContent = turn?.note || (index ? 'A saved improvement to the plant design.' : 'Start with unseparated feed. The recorded run will add and tune the separation columns.');
  $('equipment').replaceChildren();
  if (!currentNodes.length) { const o = new Option('No installed equipment', ''); $('equipment').append(o); }
  for (const n of currentNodes) $('equipment').append(new Option(n.product ? `Storage / ${n.name}` : `${n.tag} / ${n.p || 'FEED'}`, n.p));
  $('prev').disabled = index === 0; $('next').disabled = index === T.length - 1;
  inspect(); chart();
}
const views = {
  overview: { position: [154, 116, 159], target: [10, 0, 0] },
  process: { position: [55, 45, 66], target: [-3, 7, 0] },
  storage: { position: [storageX + 53, 35, 55], target: [storageX + 9, 3, 0] },
  plan: { position: [12, 205, .2], target: [12, 0, 0] },
};
let cameraTween = null;
function fittedView(id) {
  const view = views[id];
  if (!['overview', 'plan'].includes(id)) return view;
  const target = new THREE.Vector3(...view.target);
  const direction = new THREE.Vector3(...view.position).sub(target).normalize();
  const probe = new THREE.PerspectiveCamera(camera.fov, camera.aspect, .1, 700);
  probe.position.copy(target).add(direction); probe.lookAt(target);
  const inverse = probe.quaternion.clone().invert();
  const vertical = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * .83;
  const horizontal = vertical * camera.aspect;
  let distance = 0;
  for (const x of [-halfWidth - 44, halfWidth + 64]) for (const y of [0, 28]) for (const z of [-49, 49]) {
    const point = new THREE.Vector3(x, y, z).sub(target).applyQuaternion(inverse);
    distance = Math.max(distance, point.z + Math.abs(point.x) / horizontal, point.z + Math.abs(point.y) / vertical);
  }
  return { target: view.target, position: target.clone().addScaledVector(direction, distance).toArray() };
}
function setView(position, target) {
  if (reduced) { camera.position.set(...position); controls.target.set(...target); controls.update(); return; }
  cameraTween = { from: camera.position.clone(), to: new THREE.Vector3(...position), oldTarget: controls.target.clone(), target: new THREE.Vector3(...target), start: performance.now() };
}
for (const [id, view] of Object.entries(views)) $(id).onclick = () => {
  for (const key of Object.keys(views)) $(key).setAttribute('aria-pressed', String(key === id));
  const fitted = fittedView(id); setView(fitted.position, fitted.target);
};
controls.addEventListener('start', () => { cameraTween = null; });
$('focus').onclick = () => { const n = currentNodes.find(n => n.p === selected); if (n) { for (const key of Object.keys(views)) $(key).setAttribute('aria-pressed', 'false'); setView([n.x + 27, n.height + 15, n.z + 32], [n.x, n.height * .55, n.z]); $('viewport').scrollIntoView({ behavior: reduced ? 'instant' : 'smooth', block: 'start' }); } };
$('equipment').onchange = e => { selected = e.target.value; inspect(); };
$('connections').onclick = () => { showConnections = !showConnections; $('connections').setAttribute('aria-pressed', String(showConnections)); $('connections').textContent = showConnections ? 'Hide connections' : 'Show connections'; refreshConnections(); };
function stop() { playing = false; clearTimeout(timer); $('play').textContent = 'Replay assembly'; }
function tick() { if (index === T.length - 1) { stop(); return; } show(index + 1); timer = setTimeout(tick, +$('speed').value); }
$('play').onclick = () => { if (playing) { stop(); return; } if (index === T.length - 1) show(0); playing = true; $('play').textContent = 'Pause'; timer = setTimeout(tick, +$('speed').value); };
$('speed').onchange = () => { if (playing) { clearTimeout(timer); timer = setTimeout(tick, +$('speed').value); } };
$('timeline').max = T.length - 1;
$('timeline').oninput = e => { stop(); show(+e.target.value, false); };
$('prev').onclick = () => { stop(); show(index - 1); };
$('next').onclick = () => { stop(); show(index + 1); };
$('best').onclick = () => { stop(); show(T.length - 1, false); };
const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
let pointerStart;
renderer.domElement.addEventListener('pointerdown', e => { pointerStart = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', e => {
  if (!pointerStart || Math.hypot(e.clientX - pointerStart[0], e.clientY - pointerStart[1]) > 5 || e.button !== 0) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.set((e.clientX - rect.left) / rect.width * 2 - 1, -(e.clientY - rect.top) / rect.height * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  for (const hit of raycaster.intersectObjects(currentNodes.map(n => n.object), true)) {
    let object = hit.object;
    while (object && object.userData.path === undefined) object = object.parent;
    if (object) { selected = object.userData.path; inspect(); break; }
  }
});
renderer.domElement.addEventListener('keydown', e => {
  if (e.key === 'Home') { e.preventDefault(); $('overview').click(); }
  if (e.key === '+' || e.key === '-') { e.preventDefault(); camera.position.sub(controls.target).multiplyScalar(e.key === '+' ? .9 : 1.1).add(controls.target); controls.update(); }
});
new ResizeObserver(() => {
  const bounds = $('viewport').getBoundingClientRect();
  renderer.setSize(bounds.width, bounds.height, false); camera.aspect = bounds.width / bounds.height; camera.updateProjectionMatrix();
  for (const id of ['overview', 'plan']) if ($(id).getAttribute('aria-pressed') === 'true') {
    const fitted = fittedView(id); cameraTween = null; camera.position.set(...fitted.position); controls.target.set(...fitted.target); controls.update();
  }
}).observe($('viewport'));
function labelPosition(element, point) {
  const q = point.clone().project(camera), visible = q.z < 1 && Math.abs(q.x) < .97 && Math.abs(q.y) < .95;
  element.style.display = visible ? 'block' : 'none';
  element.style.left = (q.x * .5 + .5) * renderer.domElement.clientWidth + 'px';
  element.style.top = (-q.y * .5 + .5) * renderer.domElement.clientHeight + 'px';
}
function frame(now) {
  if (cameraTween) {
    const t = Math.min(1, (now - cameraTween.start) / 750), ease = 1 - Math.pow(1 - t, 3);
    camera.position.lerpVectors(cameraTween.from, cameraTween.to, ease);
    controls.target.lerpVectors(cameraTween.oldTarget, cameraTween.target, ease);
    if (t === 1) cameraTween = null;
  }
  const growthT = reduced ? 1 : Math.min(1, (now - growthStart) / 900);
  growth.forEach(g => { g.scale.y = .02 + .98 * (1 - Math.pow(1 - growthT, 3)); });
  controls.update(); renderer.render(scene, camera);
  const wideView = camera.position.distanceTo(controls.target) > 100;
  for (const l of labels) { if (wideView) labelPosition(l.e, l.p); else l.e.style.display = 'none'; }
  const n = currentNodes.find(n => n.p === selected);
  if (n) labelPosition(selectionLabel, new THREE.Vector3(n.x, n.height + 2, n.z));
}
camera.position.set(...views.overview.position); controls.target.set(...views.overview.target); controls.update();
$('run').textContent = `${DATA.summary.model || 'Agent'} / ${R.budget} calls`;
show(T.length - 1, false);
$('loading').style.display = 'none';
renderer.setAnimationLoop(frame);
