/**
 * Typed fetch client for the Python API.
 */

const DEFAULT_API_BASE = "http://127.0.0.1:8000";

export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? DEFAULT_API_BASE;
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

/** GeoJSON returned by ``GET /spacecraft/map-positions`` (Mapbox-compatible). */
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
  options?: { duration_minutes?: number; step_seconds?: number },
): Promise<TrajectoryResponse> {
  const params = new URLSearchParams();
  params.set("include_llh", "true");
  if (options?.duration_minutes != null) {
    params.set("duration_minutes", String(options.duration_minutes));
  }
  if (options?.step_seconds != null) {
    params.set("step_seconds", String(options.step_seconds));
  }
  const path = `/spacecraft/${encodeURIComponent(satId)}/trajectory?${params}`;
  const res = await fetch(`${getApiBaseUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new ApiError(`Failed to load trajectory: ${res.status}`, res.status);
  }
  return (await res.json()) as TrajectoryResponse;
}
