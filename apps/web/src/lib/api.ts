/**
 * Typed fetch client for the Python API.
 *
 * In `next dev`, the browser defaults to same-origin `/node-api` (rewritten by `next.config.js`).
 * Set `NODE_API_UPSTREAM` (e.g. `http://127.0.0.1:8001`) so the proxy matches your uvicorn port.
 */

const DEFAULT_SERVER_API = "http://127.0.0.1:8000";
const BROWSER_PROXY_PREFIX = "/node-api";

function isDefaultLoopbackApiBase(url: string): boolean {
  const u = url.replace(/\/$/, "");
  return u === "http://127.0.0.1:8000" || u === "http://localhost:8000";
}

export function getApiBaseUrl(): string {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? "";
  const explicit = raw ? raw.replace(/\/$/, "") : "";
  const forceDirect = process.env.NEXT_PUBLIC_API_FORCE_DIRECT === "1";

  if (typeof window !== "undefined") {
    const isDev = process.env.NODE_ENV === "development";
    if (explicit && (!isDev || forceDirect || !isDefaultLoopbackApiBase(explicit))) {
      return explicit;
    }
    if (isDev) return BROWSER_PROXY_PREFIX;
    return explicit || DEFAULT_SERVER_API;
  }

  if (explicit) return explicit;
  const upstream = process.env.NODE_API_UPSTREAM?.trim();
  return (upstream && upstream.replace(/\/$/, "")) || DEFAULT_SERVER_API;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch(`${getApiBaseUrl()}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Health check failed: ${res.status}`, res.status);
  }
  return (await res.json()) as { status: string };
}

export async function postAgentTurn(
  body: import("@/lib/types").AgentTurnRequest,
): Promise<import("@/lib/types").AgentTurnResponse> {
  const res = await fetch(`${getApiBaseUrl()}/agent/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const raw = await res.text().catch(() => res.statusText);
    let detail = raw;
    try {
      const j = JSON.parse(raw) as { detail?: unknown };
      if (typeof j.detail === "string") detail = j.detail;
      else if (Array.isArray(j.detail))
        detail = j.detail.map((x: { msg?: string }) => x?.msg ?? JSON.stringify(x)).join("; ");
    } catch {
      /* keep raw */
    }
    throw new ApiError(`Agent turn failed (${res.status}): ${detail}`, res.status);
  }
  return (await res.json()) as import("@/lib/types").AgentTurnResponse;
}

export type SpacecraftSummary = {
  sat_id: string;
  name: string;
  norad_catalog_id: number;
  purpose: string;
  ephemeris_epoch_utc: string;
  updated_at: string;
};

export async function fetchSpacecraftList(): Promise<SpacecraftSummary[]> {
  const res = await fetch(`${getApiBaseUrl()}/spacecraft/`, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Failed to load spacecraft: ${res.status}`, res.status);
  }
  return (await res.json()) as SpacecraftSummary[];
}

/** GeoJSON returned by ``GET /spacecraft/map-positions`` (e.g. Mapbox or Three.js clients). */
export type SpacecraftMapGeoJSON = {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      sat_id: string;
      name: string;
      norad_catalog_id: number;
      purpose: string;
    };
  }>;
};

export async function fetchSpacecraftMapPositions(maxCount = 20_000): Promise<SpacecraftMapGeoJSON> {
  const url = `${getApiBaseUrl()}/spacecraft/map-positions?max_count=${maxCount}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Failed to load map positions: ${res.status}`, res.status);
  }
  return (await res.json()) as SpacecraftMapGeoJSON;
}

/** One row from ``GET /spacecraft/tle-bundle`` for client-side SGP4. */
export type TleBundleItem = {
  sat_id: string;
  name: string;
  norad_catalog_id: number;
  purpose: string;
  tle_line1: string;
  tle_line2: string;
};

export async function fetchSpacecraftTleBundle(maxCount = 20_000): Promise<TleBundleItem[]> {
  const url = `${getApiBaseUrl()}/spacecraft/tle-bundle?max_count=${maxCount}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Failed to load TLE bundle: ${res.status}`, res.status);
  }
  return (await res.json()) as TleBundleItem[];
}

/** Row from ``GET /spacecraft/kepler-catalog`` (OE matches physics slate / ``propagate_oe``). */
export type KeplerCatalogRow = {
  sat_id: string;
  name: string;
  norad_catalog_id: number;
  purpose: string;
  ephemeris_epoch_utc: string;
  oe: number[];
};

export async function fetchSpacecraftKeplerCatalog(maxCount = 20_000): Promise<KeplerCatalogRow[]> {
  const url = `${getApiBaseUrl()}/spacecraft/kepler-catalog?max_count=${maxCount}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Failed to load Kepler catalog: ${res.status}`, res.status);
  }
  return (await res.json()) as KeplerCatalogRow[];
}

export type TrajectorySample = {
  epoch_utc: string;
  position_km: number[];
  velocity_km_s: number[];
  lon_deg: number | null;
  lat_deg: number | null;
};

export type TrajectoryResponse = {
  sat_id: string;
  samples: TrajectorySample[];
};

export async function fetchSpacecraftTrajectory(
  satId: string,
  options?: { duration_minutes?: number; step_seconds?: number; start_utc?: string },
): Promise<TrajectoryResponse> {
  const params = new URLSearchParams();
  params.set("include_llh", "false");
  if (options?.duration_minutes != null) {
    params.set("duration_minutes", String(options.duration_minutes));
  }
  if (options?.step_seconds != null) {
    params.set("step_seconds", String(options.step_seconds));
  }
  if (options?.start_utc) {
    params.set("start_utc", options.start_utc);
  }
  const path = `/spacecraft/${encodeURIComponent(satId)}/trajectory?${params}`;
  const res = await fetch(`${getApiBaseUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Failed to load trajectory: ${res.status}`, res.status);
  }
  return (await res.json()) as TrajectoryResponse;
}

export type ManeuverPreviewBurnBody = {
  epoch_utc: string;
  delta_v_mps: { x: number; y: number; z: number };
  frame?: string;
};

/** POST /spacecraft/{sat_id}/trajectory-preview-maneuvers — SGP4 + impulsive ECI Δv (preview only). */
export async function postTrajectoryPreviewManeuvers(
  satId: string,
  body: {
    start_utc: string;
    duration_minutes?: number;
    step_seconds?: number;
    maneuvers: ManeuverPreviewBurnBody[];
  },
): Promise<TrajectoryResponse> {
  const res = await fetch(
    `${getApiBaseUrl()}/spacecraft/${encodeURIComponent(satId)}/trajectory-preview-maneuvers`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    const t = await res.text().catch(() => res.statusText);
    throw new ApiError(`Trajectory preview failed: ${t}`, res.status);
  }
  return (await res.json()) as TrajectoryResponse;
}

export type CatalogScreenEvent = {
  id: string;
  primary_sat_id: string;
  secondary_sat_id: string;
  tca_utc: string;
  miss_distance_km: number;
  pc_heuristic: number;
  sphere_radius_km: number;
  eci_mid_m: [number, number, number];
  /** SGP4 primary position at TCA (m, TEME/ECI-like — same frame as globe fleet). */
  primary_eci_m: [number, number, number];
  secondary_eci_m: [number, number, number];
};

export type CatalogScreenResponse = {
  sim_utc: string;
  events: CatalogScreenEvent[];
};

export type CatalogScreenManeuverBurn = {
  epoch_utc: string;
  delta_v_mps: { x: number; y: number; z: number };
  frame?: string;
};

export async function postCatalogConjunctionScreen(
  body: {
    sim_utc: string;
    separation_prefilter_km?: number;
    max_satellites?: number;
    sphere_radius_km?: number;
    step_s?: number;
    search_max_orbits?: number;
    /** When set with ECI burns, server re-checks TCA separation vs preview trajectory (TLEs unchanged). */
    maneuver_preview_sat_id?: string;
    maneuver_preview_maneuvers?: CatalogScreenManeuverBurn[];
  },
): Promise<CatalogScreenResponse> {
  const res = await fetch(`${getApiBaseUrl()}/conjunctions/catalog-screen`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text().catch(() => res.statusText);
    throw new ApiError(`Catalog screen failed: ${t}`, res.status);
  }
  return (await res.json()) as CatalogScreenResponse;
}

/** Two-body Lambert chord (same solver as mission / avoidance stack). */
export type PlannerLambertChordRequest = {
  r0_m: [number, number, number];
  r_m: [number, number, number];
  tof_s: number;
  mu_m3_s2?: number;
  prograde?: boolean;
};

export type PlannerLambertChordResponse = {
  v0_mps: number[];
  v1_mps: number[];
  mu_m3_s2: number;
};

export async function postPlannerLambertChord(
  body: PlannerLambertChordRequest,
): Promise<PlannerLambertChordResponse> {
  const res = await fetch(`${getApiBaseUrl()}/planner/lambert/chord`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text().catch(() => res.statusText);
    throw new ApiError(`Lambert chord failed: ${t}`, res.status);
  }
  return (await res.json()) as PlannerLambertChordResponse;
}
