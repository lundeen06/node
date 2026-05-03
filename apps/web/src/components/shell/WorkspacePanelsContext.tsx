"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

const LS_FLEET_W = "node-ops-fleet-panel-w";
const LS_AGENT_W = "node-ops-agent-panel-w";

const DEFAULT_FLEET_W = 280;
const DEFAULT_AGENT_W = 340;
const MIN_FLEET_W = 200;
const MAX_FLEET_W = 560;
const MIN_AGENT_W = 260;
const MAX_AGENT_W = 640;

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

function readStoredInt(key: string, fallback: number): number {
  if (typeof window === "undefined") return fallback;
  const raw = localStorage.getItem(key);
  const n = raw == null ? NaN : Number.parseInt(raw, 10);
  return Number.isFinite(n) ? n : fallback;
}

export type WorkspacePanelsValue = {
  fleetWidth: number;
  agentWidth: number;
  setFleetWidth: (w: number) => void;
  setAgentWidth: (w: number) => void;
};

const WorkspacePanelsContext = createContext<WorkspacePanelsValue | null>(null);

export function WorkspacePanelsProvider({ children }: { children: ReactNode }) {
  const [hydrated, setHydrated] = useState(false);
  const [fleetWidth, setFleetWidthState] = useState(DEFAULT_FLEET_W);
  const [agentWidth, setAgentWidthState] = useState(DEFAULT_AGENT_W);

  useEffect(() => {
    setFleetWidthState(clamp(readStoredInt(LS_FLEET_W, DEFAULT_FLEET_W), MIN_FLEET_W, MAX_FLEET_W));
    setAgentWidthState(clamp(readStoredInt(LS_AGENT_W, DEFAULT_AGENT_W), MIN_AGENT_W, MAX_AGENT_W));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(LS_FLEET_W, String(Math.round(fleetWidth)));
  }, [fleetWidth, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem(LS_AGENT_W, String(Math.round(agentWidth)));
  }, [agentWidth, hydrated]);

  const setFleetWidth = useCallback((w: number) => {
    setFleetWidthState(clamp(w, MIN_FLEET_W, MAX_FLEET_W));
  }, []);

  const setAgentWidth = useCallback((w: number) => {
    setAgentWidthState(clamp(w, MIN_AGENT_W, MAX_AGENT_W));
  }, []);

  const value = useMemo<WorkspacePanelsValue>(
    () => ({
      fleetWidth,
      agentWidth,
      setFleetWidth,
      setAgentWidth,
    }),
    [fleetWidth, agentWidth, setFleetWidth, setAgentWidth],
  );

  return <WorkspacePanelsContext.Provider value={value}>{children}</WorkspacePanelsContext.Provider>;
}

export function useWorkspacePanels(): WorkspacePanelsValue {
  const ctx = useContext(WorkspacePanelsContext);
  if (!ctx) {
    throw new Error("useWorkspacePanels must be used within WorkspacePanelsProvider");
  }
  return ctx;
}

type ResizeEdge = "fleet-main" | "main-agent";

export function PanelResizeHandle({ edge }: { edge: ResizeEdge }) {
  const { fleetWidth, agentWidth, setFleetWidth, setAgentWidth } = useWorkspacePanels();
  const dragRef = useRef<{ pointerId: number; startX: number; startFleet: number; startAgent: number } | null>(
    null,
  );

  const endDrag = useCallback(() => {
    dragRef.current = null;
    document.body.style.removeProperty("cursor");
    document.body.style.removeProperty("user-select");
  }, []);

  const onPointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      e.preventDefault();
      dragRef.current = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startFleet: fleetWidth,
        startAgent: agentWidth,
      };
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [edge, fleetWidth, agentWidth],
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const d = dragRef.current;
      if (!d || e.pointerId !== d.pointerId) return;
      const dx = e.clientX - d.startX;
      /* Fleet: drag right widens fleet into the map. Agent: seam is on the agent’s left, so drag sign is opposite. */
      if (edge === "fleet-main") {
        setFleetWidth(d.startFleet + dx);
      } else {
        setAgentWidth(d.startAgent - dx);
      }
    },
    [edge, setFleetWidth, setAgentWidth],
  );

  const onPointerUp = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const d = dragRef.current;
      if (d && e.pointerId === d.pointerId) {
        try {
          e.currentTarget.releasePointerCapture(e.pointerId);
        } catch {
          /* already released */
        }
        endDrag();
      }
    },
    [endDrag],
  );

  const onLostPointerCapture = useCallback(() => {
    endDrag();
  }, [endDrag]);

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={edge === "fleet-main" ? "Resize fleet panel" : "Resize agent panel"}
      className="group relative z-10 flex w-3 shrink-0 cursor-col-resize touch-none select-none items-stretch justify-center"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onLostPointerCapture={onLostPointerCapture}
    >
      <span
        className="pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border group-hover:bg-muted-foreground/70 group-active:bg-muted-foreground"
        aria-hidden
      />
    </div>
  );
}
