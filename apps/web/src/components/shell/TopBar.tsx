"use client";

import { Satellite } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

import { useSimClock } from "./SimClockContext";

export function TopBar() {
  const pathname = usePathname();
  const [utc, setUtc] = useState<string>("--:--:--");
  const { getSimInstant, timeScale, setTimeScale, syncSimToWallClock, displayTick } = useSimClock();
  const [simUtc, setSimUtc] = useState<string>("--");

  useEffect(() => {
    const tick = () => setUtc(new Date().toISOString().slice(11, 19));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const tick = () => {
      const s = getSimInstant();
      setSimUtc(s.toISOString().replace("T", " ").slice(0, 19));
    };
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [getSimInstant, displayTick]);

  const navPill = (href: string, label: string, active: boolean) => (
    <Link
      href={href}
      className={cn(
        "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
        active
          ? "bg-primary/12 text-foreground shadow-sm ring-1 ring-primary/25"
          : "text-muted-foreground hover:bg-muted/80 hover:text-foreground",
      )}
    >
      {label}
    </Link>
  );

  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border/80 bg-background/90 px-4 shadow-sm backdrop-blur-md supports-[backdrop-filter]:bg-background/75">
      <div className="flex items-center gap-3">
        <Link
          href="/ops"
          className="group relative flex shrink-0 items-center rounded-lg p-0.5 ring-offset-2 ring-offset-background transition-shadow hover:ring-2 hover:ring-primary/20"
          aria-label="node home"
        >
          <span className="flex h-24 w-24 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-sm ring-1 ring-primary/15 transition-transform group-hover:scale-[1.03]">
            <Satellite className="h-14 w-14" strokeWidth={1.35} aria-hidden />
          </span>
        </Link>
      </div>

      <Separator orientation="vertical" className="h-7 bg-border/60" />

      <nav className="flex items-center gap-1 rounded-lg border border-border/50 bg-muted/20 p-0.5">
        {navPill("/ops", "Ops", pathname === "/ops" || pathname?.startsWith("/ops/"))}
        {navPill("/planner/EO-12", "Planner", Boolean(pathname?.startsWith("/planner")))}
      </nav>

      <div className="ml-auto flex flex-wrap items-center justify-end gap-2 sm:gap-3">
        <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-muted/15 px-2 py-1 shadow-sm">
          <label className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            <span className="whitespace-nowrap">Sim ×</span>
            <select
              className="cursor-pointer rounded-md border border-border/80 bg-background px-1.5 py-0.5 font-mono text-[10px] text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={String(timeScale)}
              onChange={(e) => setTimeScale(Number(e.target.value))}
              aria-label="Simulation time scale"
            >
              <option value="1">1</option>
              <option value="30">30</option>
              <option value="120">120</option>
              <option value="600">600</option>
              <option value="3600">3600</option>
            </select>
          </label>
          <Separator orientation="vertical" className="h-4 bg-border/50" />
          <button
            type="button"
            className="rounded-md px-2 py-0.5 text-[10px] font-medium text-muted-foreground transition-colors hover:bg-muted/70 hover:text-foreground"
            onClick={() => syncSimToWallClock()}
          >
            Sync → wall
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge
            variant="outline"
            className="border-primary/20 bg-primary/5 font-mono text-[10px] tabular-nums text-foreground"
            title="Simulation UTC (drives globe + screening)"
          >
            SIM {simUtc}
          </Badge>
          <Badge variant="outline" className="font-mono text-[10px] tabular-nums text-muted-foreground" title="Wall clock">
            UTC {utc}
          </Badge>
          <Badge className="border-0 bg-muted px-2 text-[10px] font-medium text-muted-foreground">demo</Badge>
        </div>
      </div>
    </header>
  );
}
