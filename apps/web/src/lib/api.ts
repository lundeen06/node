/**
 * Typed fetch client for the Python API (stubs return 501 today).
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
