"use client";

import { Globe } from "@/components/globe/Globe";

import { AgentChat } from "./AgentChat";
import { FleetPanel } from "./FleetPanel";
import { TopBar } from "./TopBar";

export function OpsWorkspace() {
  return (
    <div className="flex h-dvh min-h-0 flex-col bg-background">
      <TopBar />

      <div className="grid min-h-0 flex-1 grid-cols-[280px_1fr_340px]">
        <FleetPanel />
        <main className="relative min-h-0 border-x border-border/60 bg-zinc-950 p-2">
          <Globe />
        </main>
        <AgentChat />
      </div>
    </div>
  );
}
