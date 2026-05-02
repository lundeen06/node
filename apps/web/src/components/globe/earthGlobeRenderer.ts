import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { SMAAPass } from "three/addons/postprocessing/SMAAPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

import { createEarthRimAtmosphere } from "./earthRimAtmosphere";
import { ecefToGeodeticWgs84, type ECEF } from "@/lib/orbit/ecef";
import { EARTH_RADIUS_SCENE, ecefToSceneVector3 } from "@/lib/orbit/ecefThree";
import { getSatelliteECEF, sampleOrbitPathECEF, SATELLITE_IDS } from "@/lib/orbit/satellite-propagation";

const ORBIT_LINE_STEPS = 96;
const ORBIT_DURATION_MS = 92 * 60 * 1000;
const BASE_SAT_RADIUS_SCENE = 0.055;

const SAT_LINE_COLORS = [0x66c2ff, 0xffb366, 0x8dff9f];

const STARFIELD_RADIUS = 220;
const STAR_COUNT = 9000;

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

function satelliteRadiusScene(ecef: ECEF): number {
  const { h } = ecefToGeodeticWgs84(ecef);
  const altScale = 1 + Math.min(Math.max(0, h) / 4e6, 2.5) * 0.18;
  return BASE_SAT_RADIUS_SCENE * altScale;
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

export type EarthGlobeHandle = { dispose: () => void };

/**
 * Earth + satellites: gradient sky sphere, **PMREM** (`RoomEnvironment`), **bloom** + SMAA + ACES
 * (`OutputPass`), physical materials, dense star shell, sun-aware Fresnel atmosphere.
 */
export function attachEarthGlobe(container: HTMLElement): EarthGlobeHandle {
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
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(
    50,
    container.clientWidth / Math.max(container.clientHeight, 1),
    0.05,
    500,
  );
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
    opacity: 0.16,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  const stars = new THREE.Points(starsGeo, starsMat);
  stars.renderOrder = -1;
  scene.add(stars);

  const earthGeom = new THREE.SphereGeometry(EARTH_RADIUS_SCENE, 144, 144);
  const albedoUrl = getEarthAlbedoUrl();
  let earthMaterial: THREE.MeshPhysicalMaterial;
  let earthTexture: THREE.Texture | null = null;

  if (albedoUrl) {
    earthMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xffffff,
      metalness: 0.04,
      roughness: 0.58,
      clearcoat: 0.28,
      clearcoatRoughness: 0.32,
      specularIntensity: 1.0,
      specularColor: new THREE.Color(0xe8f4ff),
      ior: 1.38,
      envMapIntensity: 0.44,
      sheen: 0.12,
      sheenRoughness: 0.85,
      sheenColor: new THREE.Color(0x88a8cc),
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

  const satGeom = new THREE.SphereGeometry(1, 24, 24);
  const satMat = new THREE.MeshPhysicalMaterial({
    color: 0xf2f8ff,
    metalness: 0.42,
    roughness: 0.22,
    clearcoat: 0.62,
    clearcoatRoughness: 0.16,
    emissive: 0x203858,
    emissiveIntensity: 0.62,
    envMapIntensity: 0.95,
  });
  const instanced = new THREE.InstancedMesh(satGeom, satMat, SATELLITE_IDS.length);
  instanced.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  instanced.frustumCulled = false;
  scene.add(instanced);

  const orbitLines: THREE.Line[] = [];
  const vScratch = new THREE.Vector3();
  const dummy = new THREE.Object3D();

  for (let i = 0; i < SATELLITE_IDS.length; i++) {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(ORBIT_LINE_STEPS * 3);
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const line = new THREE.Line(
      g,
      new THREE.LineBasicMaterial({
        color: SAT_LINE_COLORS[i % SAT_LINE_COLORS.length],
        transparent: true,
        opacity: 0.62,
        depthWrite: false,
      }),
    );
    line.frustumCulled = false;
    orbitLines.push(line);
    scene.add(line);
  }

  const composer = new EffectComposer(renderer);
  const renderPass = new RenderPass(scene, camera);
  const pr0 = renderer.getPixelRatio();
  const w0 = container.clientWidth;
  const h0 = Math.max(container.clientHeight, 1);
  const bloomRes = new THREE.Vector2(Math.floor(w0 * pr0), Math.floor(h0 * pr0));
  const bloomPass = new UnrealBloomPass(bloomRes, 0.26, 0.52, 0.86);
  const smaaPass = new SMAAPass(Math.floor(w0 * pr0), Math.floor(h0 * pr0));
  const outputPass = new OutputPass();
  composer.addPass(renderPass);
  composer.addPass(bloomPass);
  composer.addPass(smaaPass);
  composer.addPass(outputPass);

  const syncComposerSize = () => {
    const w = container.clientWidth;
    const h = Math.max(container.clientHeight, 1);
    const pr = renderer.getPixelRatio();
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    composer.setPixelRatio(pr);
    composer.setSize(w, h);
  };
  syncComposerSize();

  const updateMeshes = (timeMs: number) => {
    for (let i = 0; i < SATELLITE_IDS.length; i++) {
      const id = SATELLITE_IDS[i]!;
      const ecef = getSatelliteECEF(timeMs, id);
      ecefToSceneVector3(ecef, vScratch);
      const r = satelliteRadiusScene(ecef);
      dummy.position.copy(vScratch);
      dummy.scale.setScalar(r);
      dummy.updateMatrix();
      instanced.setMatrixAt(i, dummy.matrix);
    }
    instanced.instanceMatrix.needsUpdate = true;

    for (let i = 0; i < orbitLines.length; i++) {
      const id = SATELLITE_IDS[i]!;
      const path = sampleOrbitPathECEF(timeMs, id, ORBIT_DURATION_MS, ORBIT_LINE_STEPS);
      const line = orbitLines[i]!;
      const attr = line.geometry.attributes.position as THREE.BufferAttribute;
      const arr = attr.array as Float32Array;
      for (let j = 0; j < path.length; j++) {
        ecefToSceneVector3(path[j]!, vScratch);
        arr[j * 3] = vScratch.x;
        arr[j * 3 + 1] = vScratch.y;
        arr[j * 3 + 2] = vScratch.z;
      }
      attr.needsUpdate = true;
      line.geometry.setDrawRange(0, path.length);
    }
  };

  let rafId = 0;
  const tick = () => {
    rafId = requestAnimationFrame(tick);
    controls.update();
    rim.updateCameraUniform(camera);
    rim.updateSunDirection(sun.position);
    updateMeshes(performance.now());
    composer.render();
  };
  rafId = requestAnimationFrame(tick);

  const ro = new ResizeObserver(syncComposerSize);
  ro.observe(container);

  return {
    dispose: () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      controls.dispose();

      outputPass.dispose();
      smaaPass.dispose();
      bloomPass.dispose();
      composer.dispose();

      backdrop.dispose();

      pmremGenerator.dispose();
      envRT.dispose();
      scene.environment = null;

      for (const line of orbitLines) {
        line.geometry.dispose();
        (line.material as THREE.Material).dispose();
      }
      orbitLines.length = 0;

      starsGeo.dispose();
      starsMat.dispose();

      rim.dispose();

      earthGeom.dispose();
      earthMaterial.dispose();
      earthTexture?.dispose();

      satGeom.dispose();
      satMat.dispose();

      renderer.dispose();
      if (renderer.domElement.parentElement === container) {
        container.removeChild(renderer.domElement);
      }
    },
  };
}
