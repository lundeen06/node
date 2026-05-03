"use client";

import { useCallback, useState } from "react";

import { ApiError, postPlannerLambertChord } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";

const DEFAULT_R0: [number, number, number] = [5_000_000, 10_000_000, 2_100_000];
const DEFAULT_R: [number, number, number] = [-14_600_000, 2_500_000, 7_000_000];

function tripletInputs(
  label: string,
  prefix: string,
  values: [number, number, number],
  onChange: (next: [number, number, number]) => void,
) {
  const axes = ["x", "y", "z"] as const;
  return (
    <div className="space-y-2">
      <div className="text-[10px] font-medium text-muted-foreground">{label}</div>
      <div className="grid grid-cols-3 gap-2">
        {axes.map((axis, i) => (
          <div key={axis}>
            <div className="text-[10px] text-muted-foreground">{prefix}.{axis} (m)</div>
            <Input
              className="mt-0.5 h-8 font-mono text-xs"
              type="number"
              value={values[i]}
              onChange={(e) => {
                const v = Number(e.target.value);
                const next: [number, number, number] = [...values];
                next[i] = Number.isFinite(v) ? v : 0;
                onChange(next);
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

export function PlannerLibraryPanel() {
  const [r0, setR0] = useState<[number, number, number]>(DEFAULT_R0);
  const [r, setR] = useState<[number, number, number]>(DEFAULT_R);
  const [tofS, setTofS] = useState(3600);
  const [muOptional, setMuOptional] = useState("");
  const [prograde, setPrograde] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = useCallback(async () => {
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const muTrim = muOptional.trim();
      const muParsed = muTrim === "" ? undefined : Number(muTrim);
      const body = {
        r0_m: r0,
        r_m: r,
        tof_s: tofS,
        prograde,
        ...(muParsed !== undefined && Number.isFinite(muParsed) && muParsed > 0
          ? { mu_m3_s2: muParsed }
          : {}),
      };
      const out = await postPlannerLambertChord(body);
      setResult(JSON.stringify(out, null, 2));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [muOptional, prograde, r, r0, tofS]);

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle className="text-xs">Lambert chord (two-body)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 p-4 pt-0 text-sm">
          <p className="text-[10px] leading-relaxed text-muted-foreground">
            Calls the API solver used elsewhere in the stack (Vallado universal variable, Earth μ from{" "}
            <span className="font-mono text-foreground">physics.propulsion.util_dyn</span> unless you override).
          </p>
          {tripletInputs("Departure r₀", "r0", r0, setR0)}
          {tripletInputs("Arrival r", "r", r, setR)}
          <div className="grid max-w-xs gap-2">
            <div>
              <div className="text-[10px] text-muted-foreground">Time of flight (s)</div>
              <Input
                className="mt-0.5 h-8 font-mono text-xs"
                type="number"
                value={tofS}
                onChange={(e) => setTofS(Number(e.target.value) || 0)}
              />
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground">μ (m³/s²), optional</div>
              <Input
                className="mt-0.5 h-8 font-mono text-xs"
                placeholder="default Earth"
                value={muOptional}
                onChange={(e) => setMuOptional(e.target.value)}
              />
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-[10px] text-muted-foreground">
              <input type="checkbox" checked={prograde} onChange={(e) => setPrograde(e.target.checked)} />
              Prograde branch
            </label>
          </div>
          <Button size="sm" className="h-8 text-xs" disabled={busy} onClick={() => void run()}>
            {busy ? "Running…" : "Run Lambert"}
          </Button>
        </CardContent>
      </Card>

      {(err || result) && (
        <Card>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-xs">{err ? "Error" : "Result"}</CardTitle>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            <Separator className="mb-3" />
            {err ? (
              <pre className="whitespace-pre-wrap break-all font-mono text-[11px] text-destructive">{err}</pre>
            ) : (
              <pre className="max-h-64 overflow-auto font-mono text-[11px] text-foreground">{result}</pre>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
