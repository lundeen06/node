/** Mapbox GL access for client-only maps. */

const DEFAULT_STYLE = "mapbox://styles/mapbox/dark-v11";

/**
 * Convert a copied Studio “Share” HTTPS URL into the `mapbox://` form Mapbox GL prefers.
 * Avoids duplicate / mismatched `access_token` query params (SDK uses `mapboxgl.accessToken`).
 */
export function normalizeMapboxStyleUrl(input: string): string {
  const trimmed = input.trim();
  const match = trimmed.match(
    /^https:\/\/api\.mapbox\.com\/styles\/v1\/([^/]+)\/([^/?#]+)(?:[?#].*)?$/i,
  );
  if (match) {
    const username = match[1];
    const styleId = match[2];
    return `mapbox://styles/${username}/${styleId}`;
  }
  return trimmed;
}

export function getMapboxAccessToken(): string | undefined {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  return token && token.length > 0 ? token.trim() : undefined;
}

/**
 * Map style URL passed to Mapbox GL `Map({ style })`.
 *
 * Prefer **`mapbox://styles/<username>/<style_id>`** (from Studio → Share → “Develop” style URL).
 * If you paste the full `https://api.mapbox.com/styles/v1/...` link, we normalize it to `mapbox://`.
 */
export function getMapboxStyleUrl(): string {
  const url = process.env.NEXT_PUBLIC_MAPBOX_STYLE_URL;
  if (url && url.length > 0) {
    return normalizeMapboxStyleUrl(url);
  }
  return DEFAULT_STYLE;
}

/**
 * Globe projection looks great with Mapbox core styles but often fails silently with custom Studio styles.
 * - Default: globe only when using the built-in dark style (no custom `NEXT_PUBLIC_MAPBOX_STYLE_URL`).
 * - Force globe: `NEXT_PUBLIC_MAPBOX_GLOBE=1`
 * - Force flat map: `NEXT_PUBLIC_MAPBOX_GLOBE=0`
 */
export function shouldUseGlobeProjection(): boolean {
  const override = process.env.NEXT_PUBLIC_MAPBOX_GLOBE?.trim();
  if (override === "0") return false;
  if (override === "1") return true;

  const hasCustomStyleEnv = Boolean(process.env.NEXT_PUBLIC_MAPBOX_STYLE_URL?.trim());
  if (hasCustomStyleEnv) return false;

  const style = getMapboxStyleUrl();
  return style.startsWith("mapbox://styles/mapbox/");
}
