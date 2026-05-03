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

export type SimClockValue = {
  /** Current simulation UTC instant (advances with wall time × time scale). */
  getSimInstant: () => Date;
  timeScale: number;
  setTimeScale: (v: number) => void;
  /** Reset sim clock to real UTC now (wall). */
  syncSimToWallClock: () => void;
  /** Bump when sim syncs — subscribe for clock UI refresh. */
  displayTick: number;
};

const SimClockContext = createContext<SimClockValue | null>(null);

const DEFAULT_SCALE = 1;

export function SimClockProvider({ children }: { children: ReactNode }) {
  const simOffsetMs = useRef(0);
  const epochWallMs = useRef(Date.now());
  const scaleRef = useRef(DEFAULT_SCALE);
  const [timeScale, setTimeScaleState] = useState(DEFAULT_SCALE);
  const [displayTick, setDisplayTick] = useState(0);

  const setTimeScale = useCallback((v: number) => {
    const clamped = Math.max(1, Math.min(86_400, v));
    scaleRef.current = clamped;
    setTimeScaleState(clamped);
  }, []);

  const syncSimToWallClock = useCallback(() => {
    simOffsetMs.current = 0;
    epochWallMs.current = Date.now();
    setDisplayTick((x) => x + 1);
  }, []);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    const loop = (t: number) => {
      const dt = (t - last) / 1000;
      last = t;
      simOffsetMs.current += dt * scaleRef.current * 1000;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, []);

  const getSimInstant = useCallback(() => new Date(epochWallMs.current + simOffsetMs.current), []);

  const value = useMemo<SimClockValue>(
    () => ({
      getSimInstant,
      timeScale,
      setTimeScale,
      syncSimToWallClock,
      displayTick,
    }),
    [getSimInstant, timeScale, setTimeScale, syncSimToWallClock, displayTick],
  );

  return <SimClockContext.Provider value={value}>{children}</SimClockContext.Provider>;
}

export function useSimClock(): SimClockValue {
  const ctx = useContext(SimClockContext);
  if (!ctx) {
    throw new Error("useSimClock must be used within SimClockProvider");
  }
  return ctx;
}
