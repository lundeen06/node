import * as THREE from "three";

/**
 * Thin Fresnel-scaled shell slightly outside the globe — limb glow only.
 * Mapbox-style globes use view-dependent scattering shaders; this is a small, controllable subset.
 */
export function createEarthRimAtmosphere(earthRadiusScene: number): {
  mesh: THREE.Mesh;
  updateCameraUniform: (camera: THREE.Camera) => void;
  updateSunDirection: (sunWorldPosition: THREE.Vector3) => void;
  dispose: () => void;
} {
  const shellRadius = earthRadiusScene * 1.0025;
  const geometry = new THREE.SphereGeometry(shellRadius, 96, 96);

  const vertexShader = `
varying vec3 vWorldNormal;
varying vec3 vWorldPosition;

void main() {
  vWorldNormal = normalize(mat3(modelMatrix) * normal);
  vec4 worldPosition = modelMatrix * vec4(position, 1.0);
  vWorldPosition = worldPosition.xyz;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

  const fragmentShader = `
uniform vec3 uCameraPosition;
uniform vec3 uSunDirection;
varying vec3 vWorldNormal;
varying vec3 vWorldPosition;

void main() {
  vec3 viewDir = normalize(uCameraPosition - vWorldPosition);
  vec3 n = normalize(vWorldNormal);
  float ndv = clamp(abs(dot(n, viewDir)), 0.0, 1.0);
  float rim = pow(1.0 - ndv, 2.05);
  float halo = pow(1.0 - ndv, 5.2);

  float sunDot = clamp(dot(n, uSunDirection), -0.35, 1.0);
  float dayMix = smoothstep(-0.1, 0.85, sunDot);
  vec3 cool = vec3(0.08, 0.28, 0.72);
  vec3 day = vec3(0.28, 0.72, 1.0);
  vec3 twilight = vec3(0.55, 0.35, 0.95);
  vec3 base = mix(cool, twilight, smoothstep(-0.2, 0.35, sunDot) * (1.0 - dayMix));
  base = mix(base, day, dayMix);

  vec3 highlight = vec3(0.75, 0.92, 1.0);
  vec3 rgb = mix(base, highlight, rim * 0.55 + halo * 0.2);
  float alpha = rim * 0.48 + halo * 0.14;
  gl_FragColor = vec4(rgb, alpha);
}
`;

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uCameraPosition: { value: new THREE.Vector3() },
      uSunDirection: { value: new THREE.Vector3(0.6, 0.35, 0.5).normalize() },
    },
    vertexShader,
    fragmentShader,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    side: THREE.DoubleSide,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.renderOrder = 1;
  mesh.frustumCulled = false;

  return {
    mesh,
    updateCameraUniform: (camera) => {
      material.uniforms.uCameraPosition.value.copy(camera.position);
    },
    updateSunDirection: (sunWorldPosition: THREE.Vector3) => {
      material.uniforms.uSunDirection.value.copy(sunWorldPosition).normalize();
    },
    dispose: () => {
      geometry.dispose();
      material.dispose();
    },
  };
}
