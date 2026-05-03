"use client";

import dynamic from "next/dynamic";

import { AgentChat } from "./AgentChat";
import { FleetPanel } from "./FleetPanel";
import { FleetCatalogProvider } from "./FleetCatalogContext";
import { OpsShellProvider } from "./OpsShellContext";
import { SimClockProvider } from "./SimClockContext";
import { TopBar } from "./TopBar";
import { cn } from "@/lib/utils";
import { PanelResizeHandle, WorkspacePanelsProvider, useWorkspacePanels } from "./WorkspacePanelsContext";

const Globe = dynamic(() => import("@/components/globe/Globe").then((m) => ({ default: m.Globe })), {
  ssr: false,
  loading: () => (
    <div className="flex min-h-0 w-full flex-1 items-center justify-center rounded-xl border border-white/10 bg-zinc-950/90 text-sm text-zinc-400 shadow-inner">
      Loading map…
    </div>
  ),
});

function OpsWorkspaceBody() {
  const { fleetWidth, agentWidth } = useWorkspacePanels();

  return (
    <div className="flex min-h-0 flex-1">
      <div
        className={cn(
          "relative flex min-h-0 shrink-0 flex-col overflow-hidden bg-background/70",
          "transition-[width] duration-200 ease-out motion-reduce:transition-none",
        )}
        style={{ width: fleetWidth }}
      >
        <div className="min-h-0 flex-1">
          <FleetPanel />
        </div>
      </div>
      <PanelResizeHandle edge="fleet-main" />

      <main className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-zinc-950 p-2">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl ring-1 ring-white/10 shadow-2xl">
          <Globe />
        </div>
      </main>

      <PanelResizeHandle edge="main-agent" />
      <div
        className={cn(
          "relative flex min-h-0 shrink-0 flex-col overflow-hidden bg-background/70",
          "transition-[width] duration-200 ease-out motion-reduce:transition-none",
        )}
        style={{ width: agentWidth }}
      >
        <div className="min-h-0 flex-1">
          <AgentChat />
        </div>
      </div>
    </div>
  );
}

export function OpsWorkspace() {
  return (
    <OpsShellProvider>
      <FleetCatalogProvider>
        <SimClockProvider>
          <div className="flex h-dvh min-h-0 flex-col bg-background">
            <TopBar />

            <WorkspacePanelsProvider>
              <OpsWorkspaceBody />
            </WorkspacePanelsProvider>
          </div>
        </SimClockProvider>
      </FleetCatalogProvider>
    </OpsShellProvider>
  );
}
