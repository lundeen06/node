import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { SMAAPass } from "three/addons/postprocessing/SMAAPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

import { gmstRadiansUtc } from "@/lib/orbit/kepler";
import { EARTH_RADIUS_SCENE, eciMetersToSceneVector3 } from "@/lib/orbit/ecefThree";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";

import { createEarthRimAtmosphere } from "./earthRimAtmosphere";

const STARFIELD_RADIUS = 220;
const STAR_COUNT = 9000;

const MAX_FLEET_POINTS = 25_000;
const MAX_TRACK_POINTS = 512;
/** One red sphere per conjunction (close-approach midpoint only). */
const MAX_CONJ_POINTS = 512;

/** One colored leg of a ground track (ECI meters). */
export type GroundTrackSegment = {
  path: [number, number, number][];
  color: number;
};

/** Impulsive Δv in ECI at a position (meters, m/s) for arrow visualization. */
export type GroundTrackBurnArrow = {
  positionEciM: [number, number, number];
  deltaVEciMps: [number, number, number];
  color: number;
};

/** Ground track: single path (nominal) or maneuver preview with colored legs + burn arrows. */
export type GroundTrack = {
  satId: string;
  /** Nominal catalog trajectory (single color). */
  path?: [number, number, number][];
  /** Maneuver preview legs (initial / transfer / final). */
  segments?: GroundTrackSegment[];
  burns?: GroundTrackBurnArrow[];
};

/** Close approach: midpoint at TCA plus optional primary/secondary SGP4 positions (meters). */
export type ConjunctionMarkerInput = {
  id: string;
  eciM: [number, number, number];
  primaryEciM?: [number, number, number];
  secondaryEciM?: [number, number, number];
};

export type SelectedMarker = {
  satId: string;
  eciM: [number, number, number];
};

function createSpaceGradientBackdrop(): { mesh: THREE.Mesh; dispose: () => void } {
  const geometry = new THREE.SphereGeometry(420, 64, 64);
  const material = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    depthTest: true,
    uniforms: {
      uTop: { value: new THREE.Color(0x050c18) },
      uHorizon: { value: new THREE.Color(0x081426) },
      uBottom: { value: new THREE.Color(0x02050c) },
      uBand: { value: new THREE.Color(0x102240) },
    },
    vertexShader: `
      varying vec3 vDir;
      void main() {
        vDir = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vDir;
      uniform vec3 uTop;
      uniform vec3 uHorizon;
      uniform vec3 uBottom;
      uniform vec3 uBand;
      void main() {
        vec3 d = normalize(vDir);
        float h = d.y;
        vec3 c = h > 0.0
          ? mix(uHorizon, uTop, smoothstep(0.0, 1.0, h))
          : mix(uHorizon, uBottom, smoothstep(0.0, 1.0, -h));
        float band = exp(-10.0 * abs(h));
        c += uBand * band * 0.14;
        gl_FragColor = vec4(c, 1.0);
      }
    `,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.renderOrder = -2;
  return {
    mesh,
    dispose: () => {
      geometry.dispose();
      material.dispose();
    },
  };
}

function getEarthAlbedoUrl(): string | undefined {
  const u = process.env.NEXT_PUBLIC_EARTH_ALBEDO_URL?.trim();
  return u && u.length > 0 ? u : undefined;
}

/** Flex + `min-h-0` often yields `clientWidth`/`clientHeight` of 0 on the first frame; WebGL / post passes must not see 0. */
function containerDrawSize(container: HTMLElement): { w: number; h: number } {
  return {
    w: Math.max(1, container.clientWidth),
    h: Math.max(1, container.clientHeight),
  };
}

function createStarfieldGeometry(radius: number, count: number): THREE.BufferGeometry {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const u = Math.random();
    const v = Math.random();
    const theta = 2 * Math.PI * u;
    const phi = Math.acos(2 * v - 1);
    const sp = Math.sin(phi);
    positions[i * 3] = radius * sp * Math.cos(theta);
    positions[i * 3 + 1] = radius * Math.cos(phi);
    positions[i * 3 + 2] = radius * sp * Math.sin(theta);
    const s = 0.35 + Math.random() * 0.65;
    colors[i * 3] = s * 0.82;
    colors[i * 3 + 1] = s * 0.86;
    colors[i * 3 + 2] = s;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
  return geo;
}

function disposeRoomEnvironmentScene(envScene: THREE.Scene): void {
  envScene.traverse((obj) => {
    if (obj instanceof THREE.Mesh) {
      obj.geometry?.dispose();
      const m = obj.material;
      if (Array.isArray(m)) m.forEach((x) => x.dispose());
      else if (m) m.dispose();
    }
  });
}

export type EarthGlobeOptions = {
  onFleetPick?: (satId: string) => void;
  /** Double-click a fleet point: camera follows this satellite (single clicks still use ``onFleetPick`` after debounce). */
  onFleetTrack?: (satId: string) => void;
  /** Double-click globe / limb: orbit target returns to Earth center and catalog conjunction focus can clear. */
  onEarthCentricFocus?: () => void;
  /** GMST / fleet animation use this instant; omit for wall clock. */
  getSimInstant?: () => Date;
  onConjunctionPick?: (conjunctionId: string) => void;
};

export type EarthGlobeCameraTrack =
  | { kind: "none" }
  | { kind: "satellite"; satId: string }
  | { kind: "conjunction"; id: string };

export type EarthGlobeHandle = {
  dispose: () => void;
  setFleetPositions: (items: { satId: string; eciM: [number, number, number] }[] | null) => void;
  setGroundTracks: (tracks: GroundTrack[] | null) => void;
  setSelectedMarkers: (markers: SelectedMarker[] | null) => void;
  setConjunctionMarkers: (items: ConjunctionMarkerInput[] | null) => void;
  pickFleetSatId: (ndcX: number, ndcY: number) => string | null;
  pickConjunctionId: (ndcX: number, ndcY: number) => string | null;
  /** Orbit camera follows this world point each frame until the user drags the view or track is cleared. */
  setCameraTrack: (t: EarthGlobeCameraTrack) => void;
  /** Read-only: lets React layers keep propagating a target after catalog hits drop or folders hide. */
  getCameraTrack: () => EarthGlobeCameraTrack;
};

/** Pleasant amber→cyan rotation for selected ground tracks. */
const TRACK_COLORS: number[] = [0xfbbf24, 0x60a5fa, 0xa78bfa, 0x34d399, 0xf472b6, 0xfb7185, 0x22d3ee];

function trackColorFor(index: number): number {
  return TRACK_COLORS[index % TRACK_COLORS.length]!;
}

/**
 * Fleet / tracks / markers in **ECI** (m); Earth + rim rotate by **GMST** about scene Y.
 * Conjunction hits render as red points (pickable).
 */
export function attachEarthGlobe(container: HTMLElement, options?: EarthGlobeOptions): EarthGlobeHandle {
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
    logarithmicDepthBuffer: true,
    powerPreference: "high-performance",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.02;
  renderer.setClearColor(0x02050c, 1);
  const initial = containerDrawSize(container);
  renderer.setSize(initial.w, initial.h);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(50, initial.w / initial.h, 0.05, 500);
  camera.position.set(14, 10, 14);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  /** Scene units ≈ 1000 km; small values let you dolly close to a tracked sat / TCA pair. */
  controls.minDistance = 0.06;
  controls.maxDistance = 140;
  controls.target.set(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0x9ec8f8, 0x060a12, 0.32));
  scene.add(new THREE.AmbientLight(0x8899b0, 0.34));
  const sun = new THREE.DirectionalLight(0xfff8f0, 1.72);
  sun.position.set(48, 26, 38);
  scene.add(sun);

  const backdrop = createSpaceGradientBackdrop();
  scene.add(backdrop.mesh);

  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  pmremGenerator.compileEquirectangularShader();
  const roomEnv = new RoomEnvironment();
  const envRT = pmremGenerator.fromScene(roomEnv, 0.035);
  disposeRoomEnvironmentScene(roomEnv);
  scene.environment = envRT.texture;

  const starsGeo = createStarfieldGeometry(STARFIELD_RADIUS, STAR_COUNT);
  const starsMat = new THREE.PointsMaterial({
    size: 0.014,
    sizeAttenuation: true,
    vertexColors: true,
    transparent: true,
    opacity: 0.92,
    depthWrite: false,
  });
  const stars = new THREE.Points(starsGeo, starsMat);
  scene.add(stars);

  const earthGeom = new THREE.SphereGeometry(EARTH_RADIUS_SCENE, 96, 96);
  const albedoUrl = getEarthAlbedoUrl();
  let earthMaterial: THREE.MeshPhysicalMaterial;
  let earthTexture: THREE.Texture | undefined;

  if (albedoUrl) {
    earthMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xffffff,
      metalness: 0.03,
      roughness: 0.78,
      envMapIntensity: 0.35,
    });
    const loader = new THREE.TextureLoader();
    loader.load(
      albedoUrl,
      (tex) => {
        earthTexture = tex;
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
        tex.wrapS = THREE.ClampToEdgeWrapping;
        tex.wrapT = THREE.ClampToEdgeWrapping;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.generateMipmaps = true;
        tex.flipY = true;
        earthMaterial.map = tex;
        earthMaterial.needsUpdate = true;
      },
      undefined,
      (err) => {
        console.warn("[EarthGlobe] Earth texture failed to load; using fallback material.", err);
      },
    );
  } else {
    earthMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x1c2a38,
      metalness: 0.08,
      roughness: 0.88,
      emissive: 0x05080c,
      emissiveIntensity: 0.38,
      clearcoat: 0,
      envMapIntensity: 0.45,
    });
  }

  const earth = new THREE.Mesh(earthGeom, earthMaterial);
  const rim = createEarthRimAtmosphere(EARTH_RADIUS_SCENE);
  const earthEciGroup = new THREE.Group();
  earthEciGroup.add(earth);
  earthEciGroup.add(rim.mesh);
  scene.add(earthEciGroup);

  /* Fleet points: built-in ``PointsMaterial`` so it inherits the renderer's logarithmic depth state. */
  const fleetSatIds: string[] = [];
  let fleetDrawCount = 0;
  const raycaster = new THREE.Raycaster();
  raycaster.params.Points = { threshold: 0.18 };
  raycaster.params.Line = { threshold: 0.14 };
  /** Ray distance (scene units): conjunction hit within this of a fleet hit wins picking / dbl-click. */
  const CONJ_OVER_FLEET_DEPTH_EPS = 0.06;
  const vScratch = new THREE.Vector3();
  const vTrackScene = new THREE.Vector3();
  const vTrackDelta = new THREE.Vector3();
  const vBurnOrigin = new THREE.Vector3();
  const vBurnDir = new THREE.Vector3();
  const conjPlacement = new THREE.Object3D();

  /** Latest fleet ECI (m) per sat — updated whenever ``setFleetPositions`` runs (for camera follow). */
  const lastFleetEciM = new Map<string, [number, number, number]>();
  /** Close-approach midpoint ECI (m) per event id — updated in ``setConjunctionMarkers``. */
  const lastConjMidEciM = new Map<string, [number, number, number]>();

  let cameraTrack: EarthGlobeCameraTrack = { kind: "none" };
  const setCameraTrack = (t: EarthGlobeCameraTrack) => {
    cameraTrack = t;
  };

  /** World-units point size for unselected fleet satellites (``PointsMaterial`` + ``sizeAttenuation``). */
  const FLEET_POINT_SIZE_SCENE = 0.055;
  /**
   * Selected-satellite sphere radius in scene units (1 unit ≈ 1000 km).
   * Close-approach markers use instanced meshes with this same radius so they match selected
   * satellites and read ~2× the unselected fleet point footprint.
   */
  const SELECTED_MARKER_RADIUS_SCENE = FLEET_POINT_SIZE_SCENE;
  /** Nudge markers slightly outward from Earth center (scene units ≈ km) to reduce limb z-fighting. */
  const SELECTED_MARKER_RADIAL_BUMP_SCENE = SELECTED_MARKER_RADIUS_SCENE * (1 / 3);

  const fleetPositions = new Float32Array(MAX_FLEET_POINTS * 3);
  const fleetGeo = new THREE.BufferGeometry();
  fleetGeo.setAttribute("position", new THREE.BufferAttribute(fleetPositions, 3));
  fleetGeo.setDrawRange(0, 0);
  const fleetMat = new THREE.PointsMaterial({
    color: 0x38bdf8,
    size: FLEET_POINT_SIZE_SCENE,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.95,
    depthWrite: true,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });
  const fleetPoints = new THREE.Points(fleetGeo, fleetMat);
  fleetPoints.frustumCulled = false;
  fleetPoints.renderOrder = 8;
  fleetPoints.visible = false;
  scene.add(fleetPoints);

  const conjIds: string[] = [];
  let conjDrawCount = 0;
  const conjSphereGeo = new THREE.SphereGeometry(SELECTED_MARKER_RADIUS_SCENE, 22, 22);
  const conjSphereMat = new THREE.MeshBasicMaterial({
    color: 0xef4444,
    transparent: true,
    opacity: 0.98,
    depthWrite: false,
    depthTest: true,
  });
  const conjInstanced = new THREE.InstancedMesh(conjSphereGeo, conjSphereMat, MAX_CONJ_POINTS);
  conjInstanced.frustumCulled = false;
  conjInstanced.visible = false;
  conjInstanced.count = 0;
  conjInstanced.renderOrder = 40;
  scene.add(conjInstanced);

  const setFleetPositions = (items: { satId: string; eciM: [number, number, number] }[] | null) => {
    fleetSatIds.length = 0;
    lastFleetEciM.clear();
    if (!items?.length) {
      fleetDrawCount = 0;
      fleetGeo.setDrawRange(0, 0);
      fleetPoints.visible = false;
      return;
    }
    const n = Math.min(items.length, MAX_FLEET_POINTS);
    for (let i = 0; i < n; i++) {
      const it = items[i]!;
      fleetSatIds.push(it.satId);
      lastFleetEciM.set(it.satId, it.eciM);
      eciMetersToSceneVector3(it.eciM, vScratch);
      fleetPositions[i * 3] = vScratch.x;
      fleetPositions[i * 3 + 1] = vScratch.y;
      fleetPositions[i * 3 + 2] = vScratch.z;
    }
    fleetDrawCount = n;
    const attr = fleetGeo.attributes.position as THREE.BufferAttribute;
    attr.needsUpdate = true;
    fleetGeo.setDrawRange(0, n);
    fleetPoints.visible = true;
  };

  const setConjunctionMarkers = (items: ConjunctionMarkerInput[] | null) => {
    conjIds.length = 0;
    lastConjMidEciM.clear();

    let o = 0;
    const push = (conjunctionId: string, p: [number, number, number]) => {
      if (o >= MAX_CONJ_POINTS) return;
      conjIds.push(conjunctionId);
      eciMetersToSceneVector3(p, vScratch);
      const L = vScratch.length();
      if (L > 1e-6) {
        vScratch.multiplyScalar((L + SELECTED_MARKER_RADIAL_BUMP_SCENE) / L);
      }
      conjPlacement.position.copy(vScratch);
      conjPlacement.rotation.set(0, 0, 0);
      conjPlacement.scale.set(1, 1, 1);
      conjPlacement.updateMatrix();
      conjInstanced.setMatrixAt(o, conjPlacement.matrix);
      o += 1;
    };

    if (!items?.length) {
      conjDrawCount = 0;
      conjInstanced.count = 0;
      conjInstanced.instanceMatrix.needsUpdate = true;
      conjInstanced.visible = false;
      return;
    }

    for (const it of items) {
      if (o >= MAX_CONJ_POINTS) break;
      lastConjMidEciM.set(it.id, it.eciM);
      push(it.id, it.eciM);
    }
    conjDrawCount = o;
    conjInstanced.count = o;
    conjInstanced.instanceMatrix.needsUpdate = true;
    conjInstanced.visible = o > 0;
  };

  /* Ground tracks: pool of Line objects keyed by ``satId`` or ``satId__segN``. Up to MAX_TRACK_POINTS samples each. */
  type TrackEntry = {
    line: THREE.Line;
    geo: THREE.BufferGeometry;
    mat: THREE.LineBasicMaterial;
    positions: Float32Array;
  };
  const trackPool = new Map<string, TrackEntry>();

  function downsamplePath(path: [number, number, number][], maxN: number): [number, number, number][] {
    if (path.length <= maxN) return path;
    const out: [number, number, number][] = [];
    const step = (path.length - 1) / (maxN - 1);
    for (let j = 0; j < maxN; j++) {
      const idx = Math.min(path.length - 1, Math.round(j * step));
      out.push(path[idx]!);
    }
    return out;
  }

  const ensureTrack = (key: string, colorHex: number): TrackEntry => {
    const existing = trackPool.get(key);
    if (existing) {
      existing.mat.color.setHex(colorHex);
      return existing;
    }
    const positions = new Float32Array(MAX_TRACK_POINTS * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.LineBasicMaterial({
      color: colorHex,
      transparent: true,
      opacity: 0.92,
      depthWrite: false,
    });
    const line = new THREE.Line(geo, mat);
    line.frustumCulled = false;
    line.renderOrder = 2;
    scene.add(line);
    const entry: TrackEntry = { line, geo, mat, positions };
    trackPool.set(key, entry);
    return entry;
  };

  const removeTrackEntry = (key: string) => {
    const e = trackPool.get(key);
    if (!e) return;
    scene.remove(e.line);
    e.geo.dispose();
    e.mat.dispose();
    trackPool.delete(key);
  };

  const burnPool = new Map<string, THREE.ArrowHelper>();

  const removeBurnArrow = (key: string) => {
    const h = burnPool.get(key);
    if (!h) return;
    scene.remove(h);
    h.dispose();
    burnPool.delete(key);
  };

  const updateBurnArrow = (key: string, burn: GroundTrackBurnArrow) => {
    eciMetersToSceneVector3(burn.positionEciM, vBurnOrigin);
    const dvx = burn.deltaVEciMps[0]!;
    const dvy = burn.deltaVEciMps[1]!;
    const dvz = burn.deltaVEciMps[2]!;
    const mag = Math.hypot(dvx, dvy, dvz);
    if (mag < 1e-6) return;
    vBurnDir.set(dvx, dvz, -dvy).normalize();
    const len = Math.min(3.2, Math.max(0.12, mag * 0.00235));
    const headLen = 0.28 * len;
    const headW = 0.58 * headLen;
    let helper = burnPool.get(key);
    if (!helper) {
      helper = new THREE.ArrowHelper(vBurnDir.clone(), vBurnOrigin.clone(), len, burn.color, headLen, headW);
      helper.renderOrder = 22;
      scene.add(helper);
      burnPool.set(key, helper);
      return;
    }
    helper.position.copy(vBurnOrigin);
    helper.setDirection(vBurnDir);
    helper.setLength(len, headLen, headW);
    helper.setColor(burn.color);
    helper.visible = true;
  };

  const setGroundTracks = (tracks: GroundTrack[] | null) => {
    const wantedTracks = new Set<string>();
    const wantedBurns = new Set<string>();
    if (tracks?.length) {
      tracks.forEach((t, i) => {
        if (t.segments?.length) {
          t.segments.forEach((seg, si) => {
            if (seg.path.length < 2) return;
            const key = `${t.satId}__seg${si}`;
            wantedTracks.add(key);
            const path = downsamplePath(seg.path, MAX_TRACK_POINTS);
            const entry = ensureTrack(key, seg.color);
            entry.line.userData = { satId: t.satId };
            const n = path.length;
            for (let j = 0; j < n; j++) {
              eciMetersToSceneVector3(path[j]!, vScratch);
              entry.positions[j * 3] = vScratch.x;
              entry.positions[j * 3 + 1] = vScratch.y;
              entry.positions[j * 3 + 2] = vScratch.z;
            }
            const attr = entry.geo.attributes.position as THREE.BufferAttribute;
            attr.needsUpdate = true;
            entry.geo.setDrawRange(0, n);
            entry.line.visible = true;
          });
        } else if (t.path && t.path.length >= 2) {
          wantedTracks.add(t.satId);
          const path = downsamplePath(t.path, MAX_TRACK_POINTS);
          const entry = ensureTrack(t.satId, trackColorFor(i));
          entry.line.userData = { satId: t.satId };
          const n = path.length;
          for (let j = 0; j < n; j++) {
            eciMetersToSceneVector3(path[j]!, vScratch);
            entry.positions[j * 3] = vScratch.x;
            entry.positions[j * 3 + 1] = vScratch.y;
            entry.positions[j * 3 + 2] = vScratch.z;
          }
          const attr = entry.geo.attributes.position as THREE.BufferAttribute;
          attr.needsUpdate = true;
          entry.geo.setDrawRange(0, n);
          entry.line.visible = true;
        }
        if (t.burns?.length) {
          t.burns.forEach((burn, bi) => {
            const key = `${t.satId}__burn${bi}`;
            wantedBurns.add(key);
            updateBurnArrow(key, burn);
          });
        }
      });
    }
    for (const id of Array.from(trackPool.keys())) {
      if (!wantedTracks.has(id)) removeTrackEntry(id);
    }
    for (const id of Array.from(burnPool.keys())) {
      if (!wantedBurns.has(id)) removeBurnArrow(id);
    }
  };

  type MarkerEntry = {
    mesh: THREE.Mesh;
    geo: THREE.SphereGeometry;
    mat: THREE.MeshBasicMaterial;
  };
  const markerPool = new Map<string, MarkerEntry>();

  const applyMarkerMaterialStyle = (mat: THREE.MeshBasicMaterial, colorIndex: number) => {
    mat.color.setHex(trackColorFor(colorIndex));
    mat.transparent = true;
    mat.opacity = 0.98;
    mat.depthWrite = false;
    mat.depthTest = true;
  };

  const ensureMarkerEntry = (satId: string, colorIndex: number): MarkerEntry => {
    const existing = markerPool.get(satId);
    if (existing) {
      applyMarkerMaterialStyle(existing.mat, colorIndex);
      const pr = existing.geo.parameters.radius;
      if (Math.abs(pr - SELECTED_MARKER_RADIUS_SCENE) > 1e-9) {
        existing.mesh.geometry.dispose();
        const geo = new THREE.SphereGeometry(SELECTED_MARKER_RADIUS_SCENE, 28, 28);
        existing.mesh.geometry = geo;
        existing.geo = geo;
      }
      existing.mesh.renderOrder = 25;
      existing.mesh.userData = { satId };
      return existing;
    }
    const geo = new THREE.SphereGeometry(SELECTED_MARKER_RADIUS_SCENE, 28, 28);
    const mat = new THREE.MeshBasicMaterial();
    applyMarkerMaterialStyle(mat, colorIndex);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { satId };
    mesh.renderOrder = 25;
    scene.add(mesh);
    const entry: MarkerEntry = { mesh, geo, mat };
    markerPool.set(satId, entry);
    return entry;
  };

  const removeMarkerEntry = (satId: string) => {
    const e = markerPool.get(satId);
    if (!e) return;
    scene.remove(e.mesh);
    e.geo.dispose();
    e.mat.dispose();
    markerPool.delete(satId);
  };

  const setSelectedMarkers = (markers: SelectedMarker[] | null) => {
    const wanted = new Set<string>();
    if (markers?.length) {
      markers.forEach((m, i) => {
        wanted.add(m.satId);
        const entry = ensureMarkerEntry(m.satId, i);
        const [ex, ey, ez] = m.eciM;
        eciMetersToSceneVector3([ex, ey, ez], vScratch);
        const L = vScratch.length();
        if (L > 1e-6) {
          vScratch.multiplyScalar((L + SELECTED_MARKER_RADIAL_BUMP_SCENE) / L);
        }
        entry.mesh.userData = { satId: m.satId };
        entry.mesh.position.copy(vScratch);
        entry.mesh.visible = true;
      });
    }
    for (const id of Array.from(markerPool.keys())) {
      if (!wanted.has(id)) removeMarkerEntry(id);
    }
  };

  const pickFleetSatId = (ndcX: number, ndcY: number): string | null => {
    if (!fleetPoints.visible) return null;
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
    const fleetHits = raycaster.intersectObject(fleetPoints, false);
    const fleetHi = fleetHits[0];
    if (!fleetHi || fleetHi.index == null) return null;
    if (conjInstanced.visible && conjDrawCount > 0) {
      const conjHits = raycaster.intersectObject(conjInstanced, false);
      const conjHi = conjHits[0];
      if (conjHi && conjHi.distance <= fleetHi.distance + CONJ_OVER_FLEET_DEPTH_EPS) return null;
    }
    const idx = fleetHi.index;
    if (idx < 0 || idx >= fleetDrawCount) return null;
    return fleetSatIds[idx] ?? null;
  };

  const pickConjunctionId = (ndcX: number, ndcY: number): string | null => {
    if (!conjInstanced.visible || conjDrawCount === 0) return null;
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
    const hits = raycaster.intersectObject(conjInstanced, false);
    const hi = hits[0];
    if (!hi || hi.instanceId == null) return null;
    const idx = hi.instanceId;
    if (idx < 0 || idx >= conjDrawCount) return null;
    return conjIds[idx] ?? null;
  };

  const pickGroundTrackHit = (ndcX: number, ndcY: number): { satId: string; distance: number } | null => {
    if (trackPool.size === 0) return null;
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
    const lines = Array.from(trackPool.values())
      .map((e) => e.line)
      .filter((ln) => ln.visible);
    if (lines.length === 0) return null;
    const hits = raycaster.intersectObjects(lines, false);
    const hi = hits[0];
    if (!hi || typeof hi.distance !== "number") return null;
    const sid = (hi.object.userData as { satId?: string }).satId;
    if (!sid) return null;
    return { satId: sid, distance: hi.distance };
  };

  const pickSelectedMarkerHit = (ndcX: number, ndcY: number): { satId: string; distance: number } | null => {
    if (markerPool.size === 0) return null;
    raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
    const meshes = Array.from(markerPool.values())
      .map((e) => e.mesh)
      .filter((m) => m.visible);
    if (meshes.length === 0) return null;
    const hits = raycaster.intersectObjects(meshes, false);
    const hi = hits[0];
    if (!hi || typeof hi.distance !== "number") return null;
    const sid = (hi.object.userData as { satId?: string }).satId;
    if (!sid) return null;
    return { satId: sid, distance: hi.distance };
  };

  let pickDownX = 0;
  let pickDownY = 0;
  /** Used to skip debounced fleet ``click`` right after a conjunction ``pointerup``. */
  let lastConjunctionPointerPickAt = 0;

  let fleetClickDebounceId: number | null = null;
  const clearFleetClickDebounce = () => {
    if (fleetClickDebounceId != null) {
      window.clearTimeout(fleetClickDebounceId);
      fleetClickDebounceId = null;
    }
  };

  const ndcFromClient = (clientX: number, clientY: number) => {
    const rect = renderer.domElement.getBoundingClientRect();
    const ndcX = ((clientX - rect.left) / rect.width) * 2 - 1;
    const ndcY = -((clientY - rect.top) / rect.height) * 2 + 1;
    return { ndcX, ndcY };
  };

  const onPickPointerDown = (ev: PointerEvent) => {
    pickDownX = ev.clientX;
    pickDownY = ev.clientY;
  };
  const onPickPointerUp = (ev: PointerEvent) => {
    if (Math.hypot(ev.clientX - pickDownX, ev.clientY - pickDownY) > 6) return;
    const { ndcX, ndcY } = ndcFromClient(ev.clientX, ev.clientY);
    const cj = options?.onConjunctionPick ? pickConjunctionId(ndcX, ndcY) : null;
    if (cj && options?.onConjunctionPick) {
      lastConjunctionPointerPickAt = performance.now();
      options.onConjunctionPick(cj);
    }
  };

  const onFleetClick = (ev: MouseEvent) => {
    if (ev.button !== 0) return;
    const { ndcX, ndcY } = ndcFromClient(ev.clientX, ev.clientY);

    if (ev.detail === 2) {
      clearFleetClickDebounce();
      raycaster.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
      const earthHits = raycaster.intersectObjects([earth, rim.mesh], false);
      const earthHi = earthHits[0];
      const fleetHits = fleetPoints.visible ? raycaster.intersectObject(fleetPoints, false) : [];
      const fleetHi = fleetHits[0];
      const conjHits = conjInstanced.visible && conjDrawCount > 0 ? raycaster.intersectObject(conjInstanced, false) : [];
      const conjHi = conjHits[0];
      const earthD = earthHi?.distance ?? Infinity;
      const fleetD = fleetHi?.distance ?? Infinity;
      const conjD = conjHi?.distance ?? Infinity;
      const conjWinsFleet =
        Boolean(conjHi) && (!fleetHi || conjD <= fleetD + CONJ_OVER_FLEET_DEPTH_EPS);

      if (earthHi && earthD <= fleetD && earthD <= conjD) {
        setCameraTrack({ kind: "none" });
        options?.onEarthCentricFocus?.();
        controls.target.set(0, 0, 0);
        vScratch.subVectors(camera.position, controls.target);
        const minFromEarthCenter = EARTH_RADIUS_SCENE * 1.06;
        const len = Math.min(controls.maxDistance * 0.98, Math.max(minFromEarthCenter, vScratch.length()));
        vScratch.setLength(len);
        camera.position.copy(controls.target).add(vScratch);
        return;
      }
      if (conjWinsFleet && conjHi && conjHi.instanceId != null) {
        const cidx = conjHi.instanceId;
        if (cidx >= 0 && cidx < conjDrawCount) {
          const cid = conjIds[cidx];
          if (cid && options?.onConjunctionPick) {
            setCameraTrack({ kind: "conjunction", id: cid });
            options.onConjunctionPick(cid);
          }
        }
        return;
      }
      let bestSid: string | null = null;
      let bestD = Infinity;
      if (fleetHi && fleetHi.index != null && typeof fleetHi.distance === "number") {
        const idx = fleetHi.index;
        if (idx >= 0 && idx < fleetDrawCount) {
          const sid = fleetSatIds[idx];
          if (sid) {
            bestSid = sid;
            bestD = fleetHi.distance;
          }
        }
      }
      const markerHit = pickSelectedMarkerHit(ndcX, ndcY);
      if (markerHit && markerHit.distance < bestD) {
        bestSid = markerHit.satId;
        bestD = markerHit.distance;
      }
      const trackHit = pickGroundTrackHit(ndcX, ndcY);
      if (trackHit && trackHit.distance < bestD) {
        bestSid = trackHit.satId;
        bestD = trackHit.distance;
      }
      if (bestSid) {
        setCameraTrack({ kind: "satellite", satId: bestSid });
        options?.onFleetTrack?.(bestSid);
        return;
      }
      const id = pickFleetSatId(ndcX, ndcY);
      if (id) {
        setCameraTrack({ kind: "satellite", satId: id });
        options?.onFleetTrack?.(id);
      }
      return;
    }

    if (pickConjunctionId(ndcX, ndcY)) return;
    if (ev.detail !== 1) return;
    if (performance.now() - lastConjunctionPointerPickAt < 400) return;
    clearFleetClickDebounce();
    fleetClickDebounceId = window.setTimeout(() => {
      fleetClickDebounceId = null;
      if (!options?.onFleetPick) return;
      const id = pickFleetSatId(ndcX, ndcY);
      if (id) options.onFleetPick(id);
    }, 280);
  };

  renderer.domElement.addEventListener("pointerdown", onPickPointerDown);
  renderer.domElement.addEventListener("pointerup", onPickPointerUp);
  renderer.domElement.addEventListener("click", onFleetClick);

  const composer = new EffectComposer(renderer);
  const renderPass = new RenderPass(scene, camera);
  const pr0 = renderer.getPixelRatio();
  const { w: w0, h: h0 } = containerDrawSize(container);
  const bloomRes = new THREE.Vector2(Math.floor(w0 * pr0), Math.floor(h0 * pr0));
  const bloomPass = new UnrealBloomPass(bloomRes, 0.26, 0.52, 0.86);
  const smaaPass = new SMAAPass(Math.floor(w0 * pr0), Math.floor(h0 * pr0));
  const outputPass = new OutputPass();
  composer.addPass(renderPass);
  composer.addPass(bloomPass);
  composer.addPass(smaaPass);
  composer.addPass(outputPass);

  let lastComposerW = 0;
  let lastComposerH = 0;
  const applyComposerSize = () => {
    const { w, h } = containerDrawSize(container);
    if (Math.abs(w - lastComposerW) < 1 && Math.abs(h - lastComposerH) < 1) {
      return;
    }
    lastComposerW = w;
    lastComposerH = h;
    const pr = renderer.getPixelRatio();
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    composer.setPixelRatio(pr);
    composer.setSize(w, h);
  };

  let resizeRaf = 0;
  const scheduleComposerSize = () => {
    if (resizeRaf) return;
    resizeRaf = requestAnimationFrame(() => {
      resizeRaf = 0;
      applyComposerSize();
    });
  };
  applyComposerSize();

  let rafId = 0;
  const tick = () => {
    rafId = requestAnimationFrame(tick);
    controls.update();

    const when = options?.getSimInstant?.() ?? new Date();
    earthEciGroup.rotation.set(0, gmstRadiansUtc(when), 0);
    rim.updateCameraUniform(camera);
    rim.updateSunDirection(sun.position);

    if (cameraTrack.kind === "satellite") {
      const eci = lastFleetEciM.get(cameraTrack.satId);
      if (eci) {
        eciMetersToSceneVector3(eci, vTrackScene);
        const L = vTrackScene.length();
        if (L > 1e-6) {
          vTrackDelta.subVectors(vTrackScene, controls.target);
          controls.target.add(vTrackDelta);
          camera.position.add(vTrackDelta);
        }
      }
    } else if (cameraTrack.kind === "conjunction") {
      const eci = lastConjMidEciM.get(cameraTrack.id);
      if (eci) {
        eciMetersToSceneVector3(eci, vTrackScene);
        const L = vTrackScene.length();
        if (L > 1e-6) {
          vTrackScene.multiplyScalar((L + SELECTED_MARKER_RADIAL_BUMP_SCENE) / L);
        }
        vTrackDelta.subVectors(vTrackScene, controls.target);
        controls.target.add(vTrackDelta);
        camera.position.add(vTrackDelta);
      }
    }

    composer.render();
  };
  rafId = requestAnimationFrame(tick);

  const ro = new ResizeObserver(scheduleComposerSize);
  ro.observe(container);

  return {
    dispose: () => {
      cancelAnimationFrame(rafId);
      if (resizeRaf) {
        cancelAnimationFrame(resizeRaf);
        resizeRaf = 0;
      }
      ro.disconnect();
      clearFleetClickDebounce();
      renderer.domElement.removeEventListener("pointerdown", onPickPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPickPointerUp);
      renderer.domElement.removeEventListener("click", onFleetClick);
      controls.dispose();

      outputPass.dispose();
      smaaPass.dispose();
      bloomPass.dispose();
      composer.dispose();

      backdrop.dispose();

      pmremGenerator.dispose();
      envRT.dispose();
      scene.environment = null;

      starsGeo.dispose();
      starsMat.dispose();

      rim.dispose();

      earthGeom.dispose();
      earthMaterial.dispose();
      earthTexture?.dispose();

      fleetGeo.dispose();
      fleetMat.dispose();

      scene.remove(conjInstanced);
      conjInstanced.dispose();

      for (const id of Array.from(burnPool.keys())) removeBurnArrow(id);
      for (const id of Array.from(trackPool.keys())) removeTrackEntry(id);
      for (const id of Array.from(markerPool.keys())) removeMarkerEntry(id);

      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    },
    setFleetPositions,
    setGroundTracks,
    setSelectedMarkers,
    setConjunctionMarkers,
    pickFleetSatId,
    pickConjunctionId,
    setCameraTrack,
    getCameraTrack: () => cameraTrack,
  };
}

export function fleetItemsFromKepler(
  entries: KeplerFleetEntry[],
  whenUtc: Date,
  propagateEciM: (entry: KeplerFleetEntry, when: Date) => [number, number, number] | null,
): { satId: string; eciM: [number, number, number] }[] {
  const out: { satId: string; eciM: [number, number, number] }[] = [];
  for (const e of entries) {
    const r = propagateEciM(e, whenUtc);
    if (!r) continue;
    out.push({ satId: e.sat_id, eciM: r });
  }
  return out;
}
