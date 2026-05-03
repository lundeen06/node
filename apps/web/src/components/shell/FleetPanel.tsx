"use client";

import { ChevronRight, Eye, EyeOff, Folder, Satellite, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { FOLDER_LABELS, type FleetFolderId } from "@/lib/orbit/constellationGroups";
import type { KeplerFleetEntry } from "@/lib/orbit/keplerFleet";

import { useFleetCatalog } from "./FleetCatalogContext";
import { useOpsShell } from "./OpsShellContext";

function normalizeSearch(s: string): string {
  return s.trim().toLowerCase();
}

export function FleetPanel() {
  const { selectedSatIds, isSatSelected, toggleSatSelection, clearSatSelection } = useOpsShell();
  const [search, setSearch] = useState("");
  const { loading, error, folderIds, grouped, isFolderPlotted, toggleFolderPlot } = useFleetCatalog();

  const q = normalizeSearch(search);

  const { visibleFolderIds, folderItems } = useMemo(() => {
    if (!q) {
      return {
        visibleFolderIds: folderIds,
        folderItems: grouped,
      };
    }
    const nextIds: FleetFolderId[] = [];
    const nextMap = new Map<FleetFolderId, KeplerFleetEntry[]>();

    for (const folder of folderIds) {
      const label = (FOLDER_LABELS[folder] ?? folder).toLowerCase();
      const items = grouped.get(folder) ?? [];
      const matched = items.filter((s) => {
        const hay = `${s.name} ${s.sat_id} ${s.norad_catalog_id} ${s.purpose}`.toLowerCase();
        return hay.includes(q);
      });
      const folderMatches = label.includes(q);
      if (folderMatches) {
        nextIds.push(folder);
        nextMap.set(folder, items);
        continue;
      }
      if (matched.length > 0) {
        nextIds.push(folder);
        nextMap.set(folder, matched);
      }
    }
    return { visibleFolderIds: nextIds, folderItems: nextMap };
  }, [folderIds, grouped, q]);

  const totalCount = useMemo(
    () => Array.from(grouped.values()).reduce((n, g) => n + g.length, 0),
    [grouped],
  );

  return (
    <aside className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border/50 bg-muted/10 px-3 py-2.5">
        <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/90">Fleet</div>
        <div className="flex min-w-0 items-center gap-1">
          <div className="truncate font-mono text-[10px] text-muted-foreground">
            {loading ? "…" : `${totalCount} spacecraft`}
          </div>
        </div>
      </div>
      <Separator className="opacity-50" />
      <div className="px-2 pt-2">
        <Input
          type="search"
          placeholder="Search name, NORAD, folder…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-8 border-border/60 bg-background/80 text-xs shadow-sm"
          aria-label="Search fleet"
        />
      </div>

      {selectedSatIds.size > 0 ? (
        <div className="flex items-center justify-between gap-2 px-3 py-1.5 text-[11px] text-muted-foreground">
          <span>
            <span className="font-medium text-foreground">{selectedSatIds.size}</span> selected · orbit
            visualised
          </span>
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-sm border border-border/60 bg-background/80 px-1.5 py-0.5 text-[10px] hover:bg-muted"
            onClick={clearSatSelection}
            title="Clear selection"
          >
            <X className="h-3 w-3" /> Clear
          </button>
        </div>
      ) : null}

      <div className="h-0 min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-2 py-2">
        {error ? (
          <p className="px-2 text-[11px] text-muted-foreground">{error}</p>
        ) : folderIds.length === 0 && !loading ? (
          <p className="px-2 text-[11px] text-muted-foreground">
            No catalog rows with valid orbital elements. Ingest spacecraft so <span className="font-mono">oe_vector</span>{" "}
            is populated (register / import constellation).
          </p>
        ) : q && visibleFolderIds.length === 0 ? (
          <p className="px-2 text-[11px] text-muted-foreground">No matches for this search.</p>
        ) : (
          <div className="space-y-2">
            {(q ? visibleFolderIds : folderIds).map((folder) => {
              const items = (q ? folderItems : grouped).get(folder) ?? [];
              const label = FOLDER_LABELS[folder] ?? folder;
              const plotted = isFolderPlotted(folder);
              return (
                <div
                  key={folder}
                  className={cn(
                    "overflow-hidden rounded-md border bg-muted/20 transition-colors",
                    plotted ? "border-sky-400/50 bg-sky-500/[0.04]" : "border-border/60",
                  )}
                >
                  {/* Header row: do NOT use items-stretch — the eye button must keep its 28px height even when the folder is expanded. */}
                  <div className="flex items-center gap-1 px-1 py-1">
                    <details className="group min-w-0 flex-1">
                      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-sm px-1.5 py-1 text-xs hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
                        <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition group-open:rotate-90" />
                        <Folder
                          className={cn(
                            "h-3.5 w-3.5 shrink-0",
                            plotted ? "text-sky-300" : "text-muted-foreground",
                          )}
                        />
                        <span className="min-w-0 flex-1 truncate font-medium text-foreground">{label}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">{items.length}</span>
                      </summary>
                      <div className="mt-1 border-t border-border/50 px-1 pb-1 pt-1.5">
                        {items.map((s) => {
                          const sel = isSatSelected(s.sat_id);
                          return (
                            <button
                              key={s.sat_id}
                              type="button"
                              className={cn(
                                "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11px] transition-colors",
                                sel
                                  ? "bg-amber-500/15 text-foreground ring-1 ring-amber-500/40"
                                  : "hover:bg-muted",
                              )}
                              onClick={() => toggleSatSelection(s.sat_id)}
                              aria-pressed={sel}
                              title={sel ? "Hide orbit" : "Show orbit"}
                            >
                              <Satellite
                                className={cn(
                                  "h-3.5 w-3.5 shrink-0",
                                  sel ? "text-amber-400" : "text-muted-foreground",
                                )}
                              />
                              <div className="min-w-0 flex-1">
                                <div className="truncate font-medium text-foreground">{s.name}</div>
                                <div className="truncate font-mono text-[10px] text-muted-foreground">
                                  {s.sat_id} · NORAD {s.norad_catalog_id}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </details>
                    <button
                      type="button"
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center self-start rounded-sm border transition-colors",
                        plotted
                          ? "border-sky-400/70 bg-sky-500/20 text-sky-300 hover:bg-sky-500/30"
                          : "border-border/70 bg-background/80 text-muted-foreground hover:bg-muted",
                      )}
                      onClick={() => toggleFolderPlot(folder)}
                      title={plotted ? `Hide ${label} from globe` : `Show ${label} on globe`}
                      aria-pressed={plotted}
                      aria-label={plotted ? `Hide ${label} from globe` : `Plot ${label} on globe`}
                    >
                      {plotted ? (
                        <Eye className="h-3.5 w-3.5" strokeWidth={2.25} />
                      ) : (
                        <EyeOff className="h-3.5 w-3.5" strokeWidth={2} />
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
