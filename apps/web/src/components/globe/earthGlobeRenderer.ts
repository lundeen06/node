import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { SMAAPass } from "three/addons/postprocessing/SMAAPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

import { lonLatDegHeightToEcef } from "@/lib/orbit/ecef";
import { EARTH_RADIUS_SCENE, ecefToSceneVector3 } from "@/lib/orbit/ecefThree";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";

import { createEarthRimAtmosphere } from "./earthRimAtmosphere";

const STARFIELD_RADIUS = 220;
const STAR_COUNT = 9000;

/** Rough LEO altitude for lon/lat → ECEF when API gives only geographic coords (meters above ellipsoid). */
const DEFAULT_LEO_ALT_M = 450_000;
const MAX_FLEET_POINTS = 25_000;
const MAX_TRACK_POINTS = 512;

/** One sample of a satellite track, lon/lat in degrees. */
export type GroundTrack = {
  satId: string;
  path: [number, number][];
};

/** Position of one selected satellite (lon/lat degrees). */
export type SelectedMarker = {
  satId: string;
  lonDeg: number;
  latDeg: number;
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
  /** Fires when the user clicks the fleet (short click, minimal drag). */
  onFleetPick?: (satId: string) => void;
};

export type EarthGlobeHandle = {
  dispose: () => void;
  /**
   * Update the plotted fleet from a list of {satId, lonDeg, latDeg}. Replaces all current points.
   * Pass an empty array (or null) to clear.
   */
  setFleetPositions: (
    items: { satId: string; lonDeg: number; latDeg: number }[] | null,
  ) => void;
  /** Multi-track ground paths — one Line per selected satellite. ``null`` clears all tracks. */
  setGroundTracks: (tracks: GroundTrack[] | null) => void;
  /** Multi-marker selection ring — one sphere per selected satellite. ``null`` clears all markers. */
  setSelectedMarkers: (markers: SelectedMarker[] | null) => void;
  /** Normalized device coords (-1..1) from canvas click → catalog ``sat_id``, or null. */
  pickFleetSatId: (ndcX: number, ndcY: number) => string | null;
};

/** Pleasant amber→cyan rotation for selected ground tracks. */
const TRACK_COLORS: number[] = [0xfbbf24, 0x60a5fa, 0xa78bfa, 0x34d399, 0xf472b6, 0xfb7185, 0x22d3ee];

function trackColorFor(index: number): number {
  return TRACK_COLORS[index % TRACK_COLORS.length]!;
}

/**
 * Earth + fleet (CPU-driven Points), multi-track support, selection markers.
 * Uses ``PointsMaterial`` and ``LineBasicMaterial`` so they integrate with ``logarithmicDepthBuffer``
 * automatically. Custom shader-based propagation was removed — propagation runs on the JS side and
 * uploads positions each frame.
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
  controls.minDistance = 7;
  controls.maxDistance = 80;
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
  scene.add(earth);

  const rim = createEarthRimAtmosphere(EARTH_RADIUS_SCENE);
  scene.add(rim.mesh);

  /* Fleet points: built-in ``PointsMaterial`` so it inherits the renderer's logarithmic depth state. */
  const fleetSatIds: string[] = [];
  let fleetDrawCount = 0;
  const raycaster = new THREE.Raycaster();
  raycaster.params.Points = { threshold: 0.18 };
  const vScratch = new THREE.Vector3();

  const fleetPositions = new Float32Array(MAX_FLEET_POINTS * 3);
  const fleetGeo = new THREE.BufferGeometry();
  fleetGeo.setAttribute("position", new THREE.BufferAttribute(fleetPositions, 3));
  fleetGeo.setDrawRange(0, 0);
  const fleetMat = new THREE.PointsMaterial({
    color: 0x38bdf8,
    size: 0.055,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.95,
    depthWrite: true,
  });
  const fleetPoints = new THREE.Points(fleetGeo, fleetMat);
  fleetPoints.frustumCulled = false;
  fleetPoints.visible = false;
  scene.add(fleetPoints);

  const setFleetPositions = (
    items: { satId: string; lonDeg: number; latDeg: number }[] | null,
  ) => {
    fleetSatIds.length = 0;
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
      const ecef = lonLatDegHeightToEcef(it.lonDeg, it.latDeg, DEFAULT_LEO_ALT_M);
      ecefToSceneVector3(ecef, vScratch);
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

  /* Ground tracks: pool of Line objects keyed by ``satId``. Up to MAX_TRACK_POINTS samples each. */
  type TrackEntry = {
    line: THREE.Line;
    geo: THREE.BufferGeometry;
    mat: THREE.LineBasicMaterial;
    positions: Float32Array;
  };
  const trackPool = new Map<string, TrackEntry>();

  const ensureTrackEntry = (satId: string, colorIndex: number): TrackEntry => {
    const existing = trackPool.get(satId);
    if (existing) {
      existing.mat.color.setHex(trackColorFor(colorIndex));
      return existing;
    }
    const positions = new Float32Array(MAX_TRACK_POINTS * 3);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const mat = new THREE.LineBasicMaterial({
      color: trackColorFor(colorIndex),
      transparent: true,
      opacity: 0.92,
      depthWrite: false,
    });
    const line = new THREE.Line(geo, mat);
    line.frustumCulled = false;
    line.renderOrder = 2;
    scene.add(line);
    const entry: TrackEntry = { line, geo, mat, positions };
    trackPool.set(satId, entry);
    return entry;
  };

  const removeTrackEntry = (satId: string) => {
    const e = trackPool.get(satId);
    if (!e) return;
    scene.remove(e.line);
    e.geo.dispose();
    e.mat.dispose();
    trackPool.delete(satId);
  };

  const setGroundTracks = (tracks: GroundTrack[] | null) => {
    const wanted = new Set<string>();
    if (tracks?.length) {
      tracks.forEach((t, i) => {
        if (t.path.length < 2) return;
        wanted.add(t.satId);
        const entry = ensureTrackEntry(t.satId, i);
        const n = Math.min(t.path.length, MAX_TRACK_POINTS);
        for (let j = 0; j < n; j++) {
          const [lonDeg, latDeg] = t.path[j]!;
          const ecef = lonLatDegHeightToEcef(lonDeg, latDeg, DEFAULT_LEO_ALT_M);
          ecefToSceneVector3(ecef, vScratch);
          entry.positions[j * 3] = vScratch.x;
          entry.positions[j * 3 + 1] = vScratch.y;
          entry.positions[j * 3 + 2] = vScratch.z;
        }
        const attr = entry.geo.attributes.position as THREE.BufferAttribute;
        attr.needsUpdate = true;
        entry.geo.setDrawRange(0, n);
        entry.line.visible = true;
      });
    }
    for (const id of Array.from(trackPool.keys())) {
      if (!wanted.has(id)) removeTrackEntry(id);
    }
  };

  /* Selection markers: small glowing spheres ~120 km above ground track for each selected sat. */
  type MarkerEntry = {
    mesh: THREE.Mesh;
    geo: THREE.SphereGeometry;
    mat: THREE.MeshBasicMaterial;
  };
  const markerPool = new Map<string, MarkerEntry>();

  const ensureMarkerEntry = (satId: string, colorIndex: number): MarkerEntry => {
    const existing = markerPool.get(satId);
    if (existing) {
      existing.mat.color.setHex(trackColorFor(colorIndex));
      return existing;
    }
    const geo = new THREE.SphereGeometry(0.12, 18, 18);
    const mat = new THREE.MeshBasicMaterial({
      color: trackColorFor(colorIndex),
      transparent: true,
      opacity: 0.95,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.renderOrder = 3;
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
        const ecef = lonLatDegHeightToEcef(m.lonDeg, m.latDeg, DEFAULT_LEO_ALT_M + 120_000);
        ecefToSceneVector3(ecef, vScratch);
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
    const hits = raycaster.intersectObject(fleetPoints, false);
    const hi = hits[0];
    if (!hi || hi.index == null) return null;
    const idx = hi.index;
    if (idx < 0 || idx >= fleetDrawCount) return null;
    return fleetSatIds[idx] ?? null;
  };

  let pickDownX = 0;
  let pickDownY = 0;
  const onPickPointerDown = (ev: PointerEvent) => {
    pickDownX = ev.clientX;
    pickDownY = ev.clientY;
  };
  const onPickPointerUp = (ev: PointerEvent) => {
    if (!options?.onFleetPick) return;
    if (Math.hypot(ev.clientX - pickDownX, ev.clientY - pickDownY) > 6) return;
    const rect = renderer.domElement.getBoundingClientRect();
    const ndcX = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
    const ndcY = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
    const id = pickFleetSatId(ndcX, ndcY);
    if (id) options.onFleetPick(id);
  };
  renderer.domElement.addEventListener("pointerdown", onPickPointerDown);
  renderer.domElement.addEventListener("pointerup", onPickPointerUp);

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

  const syncComposerSize = () => {
    const { w, h } = containerDrawSize(container);
    const pr = renderer.getPixelRatio();
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    composer.setPixelRatio(pr);
    composer.setSize(w, h);
  };
  syncComposerSize();

  let rafId = 0;
  const tick = () => {
    rafId = requestAnimationFrame(tick);
    controls.update();
    rim.updateCameraUniform(camera);
    rim.updateSunDirection(sun.position);
    composer.render();
  };
  rafId = requestAnimationFrame(tick);

  const ro = new ResizeObserver(syncComposerSize);
  ro.observe(container);

  return {
    dispose: () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPickPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPickPointerUp);
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
    pickFleetSatId,
  };
}

/** Convert ``KeplerFleetEntry`` array → ``setFleetPositions`` payload using the JS Kepler propagator. */
export function fleetItemsFromKepler(
  entries: KeplerFleetEntry[],
  whenUtc: Date,
  propagateLonLat: (entry: KeplerFleetEntry, when: Date) => [number, number] | null,
): { satId: string; lonDeg: number; latDeg: number }[] {
  const out: { satId: string; lonDeg: number; latDeg: number }[] = [];
  for (const e of entries) {
    const ll = propagateLonLat(e, whenUtc);
    if (!ll) continue;
    out.push({ satId: e.sat_id, lonDeg: ll[0], latDeg: ll[1] });
  }
  return out;
}
