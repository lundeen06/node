import { MOCK_SATELLITES } from "@/lib/mock-data";

export function SatelliteLayer() {
  return (
    <div className="absolute left-4 top-4 flex flex-col gap-2">
      {MOCK_SATELLITES.map((s, idx) => (
        <div
          key={s.id}
          className="rounded-md border border-border/70 bg-background/70 px-2 py-1 text-[11px] text-muted-foreground shadow-sm backdrop-blur"
          style={{ transform: `translate(${idx * 6}px, ${idx * 10}px)` }}
        >
          <div className="font-medium text-foreground">{s.name}</div>
          <div className="font-mono text-[10px]">
            NORAD {s.norad} · {s.regime}
          </div>
        </div>
      ))}
    </div>
  );
}
