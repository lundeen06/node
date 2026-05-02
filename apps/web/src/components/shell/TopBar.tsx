"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export function TopBar() {
  const [utc, setUtc] = useState<string>("--:--:--");

  useEffect(() => {
    const tick = () => setUtc(new Date().toISOString().slice(11, 19));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <header className="flex h-12 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
      <div className="flex items-center gap-2">
        <div className="leading-tight">
          <div className="text-md font-semibold tracking-tight italic">node.</div>
        </div>
      </div>

      <Separator orientation="vertical" className="h-6" />

      <nav className="flex items-center gap-2 text-xs text-muted-foreground">
        <Link className="rounded px-2 py-1 text-foreground hover:bg-muted" href="/ops">
          Ops
        </Link>
        <Link className="rounded px-2 py-1 hover:bg-muted hover:text-foreground" href="/planner/EO-12">
          Planner
        </Link>
      </nav>

      <div className="ml-auto flex items-center gap-2">
        <Badge variant="outline" className="font-mono text-[10px]">
          UTC {utc}
        </Badge>
        <Badge>demo</Badge>
      </div>
    </header>
  );
}
