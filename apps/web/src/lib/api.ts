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

export async function postAgentTurn(
  body: import("@/lib/types").AgentTurnRequest,
): Promise<import("@/lib/types").AgentTurnResponse> {
  const res = await fetch(`${getApiBaseUrl()}/agent/turn`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new ApiError(`Agent turn failed: ${detail}`, res.status);
  }
  return (await res.json()) as import("@/lib/types").AgentTurnResponse;
}
