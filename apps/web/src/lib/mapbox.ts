/** Mapbox GL access for client-only maps. */

export function getMapboxAccessToken(): string | undefined {
  const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
  return token && token.length > 0 ? token.trim() : undefined;
}

/**
 * Map style URL passed to Mapbox GL `Map({ style })`.
 * Use `NEXT_PUBLIC_MAPBOX_STYLE_URL` for a custom style (Mapbox Studio `mapbox://` or HTTPS sprite URL).
 */
export function getMapboxStyleUrl(): string {
  const url = process.env.NEXT_PUBLIC_MAPBOX_STYLE_URL;
  if (url && url.length > 0) {
    return url.trim();
  }
  return "mapbox://styles/mapbox/dark-v11";
}
