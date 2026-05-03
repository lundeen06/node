/** Human-readable UTC for burn cards / tooltips (sim-agnostic wall label). */
export function formatBurnUtcReadable(iso: string): string {
  const ms = Date.parse(iso);
  if (!Number.isFinite(ms)) return iso;
  const d = new Date(ms);
  return `${d.toISOString().slice(0, 19).replace("T", " ")} UTC`;
}

/** T− / T+ label vs simulation clock (``simNowMs``). */
export function formatTMinusSim(simNowMs: number, burnMs: number): string {
  const dtMs = burnMs - simNowMs;
  if (Math.abs(dtMs) < 800) return "T0 (at sim now)";
  const abs = Math.abs(dtMs);
  const sign = dtMs > 0 ? "T−" : "T+";
  const sec = Math.floor(abs / 1000);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  let body: string;
  if (h > 0) body = `${h}h ${m}m ${s}s`;
  else if (m > 0) body = `${m}m ${s}s`;
  else body = `${s}s`;
  return `${sign} ${body} (sim)`;
}
