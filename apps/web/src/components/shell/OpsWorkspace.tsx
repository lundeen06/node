"use client";

import dynamic from "next/dynamic";

import { AgentChat } from "./AgentChat";
import { FleetPanel } from "./FleetPanel";
import { OpsShellProvider } from "./OpsShellContext";
import { TopBar } from "./TopBar";

const Globe = dynamic(() => import("@/components/globe/Globe").then((m) => ({ default: m.Globe })), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-0 w-full flex-1 items-center justify-center rounded-md border border-border bg-zinc-950 text-sm text-muted-foreground">
      Loading map…
    </div>
  ),
});

export function OpsWorkspace() {
  return (
    <OpsShellProvider>
      <div className="flex h-dvh min-h-0 flex-col bg-background">
        <TopBar />

        <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_340px]">
          <FleetPanel />
          {/* min-h-0 + flex-1 wrapper: next/dynamic’s shell does not grow; this div fills the grid cell so Globe can fill height. */}
          <main className="relative flex min-h-0 min-w-0 flex-col overflow-hidden border-x border-border/60 bg-zinc-950 p-2">
            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
              <Globe />
            </div>
          </main>
          <AgentChat />
        </div>
      </div>
    </OpsShellProvider>
  );
}
