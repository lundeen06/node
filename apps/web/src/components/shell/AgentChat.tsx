"use client";

import { Ban, CheckCircle2, History, Loader2, MessageSquarePlus } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ApiError, getApiBaseUrl, postAgentTurn } from "@/lib/api";
import type { AgentTurnResponse, ChatMessage, PlanResponse } from "@/lib/types";
import { useOpsShell } from "@/components/shell/OpsShellContext";
import { useSimClock } from "@/components/shell/SimClockContext";
import { computeManeuverTimelineWindowMs } from "@/lib/orbit/maneuverTimeline";
import { formatBurnUtcReadable, formatTMinusSim } from "@/lib/orbit/simClockLabels";

const OPERATOR_ID = "demo";

/** v2 bundle — multiple sessions */
const STORAGE_BUNDLE = "node-agent-chat-v2";
/** legacy single-thread keys (migrated once) */
const STORAGE_MESSAGES = "node-agent-messages";
const STORAGE_PLANS = "node-agent-plans";
const STORAGE_PLAN_ANCHOR = "node-agent-plan-anchor";

const MAX_SESSIONS = 40;

/** Append new agent plans without dropping earlier pending proposals (dedupe by ``plan_id``). */
function mergeProposedPlans(prev: PlanResponse[], incoming: PlanResponse[]): PlanResponse[] {
  const seen = new Set(prev.map((p) => p.plan_id));
  const next = [...prev];
  for (const p of incoming) {
    if (!seen.has(p.plan_id)) {
      next.push(p);
      seen.add(p.plan_id);
    }
  }
  return next;
}

const BURN_VS_SIM_MARGIN_MS = 1000;

/** True if any maneuver epoch is strictly before ``sim`` minus 1 s (aligned with API burn-epoch gate). */
function planHasBurnBeforeSimInstant(plan: PlanResponse, sim: Date): boolean {
  const simMs = sim.getTime();
  return plan.maneuvers.some((m) => {
    const t = Date.parse(m.epoch_utc);
    return !Number.isFinite(t) || t < simMs - BURN_VS_SIM_MARGIN_MS;
  });
}

/** text-xs ~15px line + py-2 (8px×2) — minimum two visible lines. */
const TEXTAREA_LINE_PX = 15;
const TEXTAREA_PAD_Y_PX = 16;
const TEXTAREA_MIN_LINES = 2;
const TEXTAREA_MIN_HEIGHT_PX = TEXTAREA_LINE_PX * TEXTAREA_MIN_LINES + TEXTAREA_PAD_Y_PX;

const GREETING: ChatMessage = {
  role: "assistant",
  content:
    "I'm here for conjunction situational awareness. Run **catalog screening** in the ops shell (the API persists hits to SQLite). For fleet-wide questions I can call **get_operator_reference** (includes **catalog_entries** with each asset's `sat_id`, NORAD id, and name — use those ids for orbit plans) plus ingest presets like `starlink` and house-rule keys like `EO-CONSTELLATION`, and **get_fleet_conjunctions** — ask about risk, timing, or orbit changes anytime.",
};

const THINKING_HINTS = [
  "Reviewing your request…",
  "Checking persisted screening events and satellite state…",
  "Calling the model…",
] as const;

type AgentPhase = "idle" | "thinking" | "typing";

type ChatSession = {
  id: string;
  title: string;
  updatedAt: string;
  messages: ChatMessage[];
  proposedPlans: PlanResponse[];
  planAnchorIndex: number | null;
  /** Passed to the API as `session_id` for this thread */
  apiSessionId: string;
};

type ChatBundle = {
  sessions: ChatSession[];
  activeSessionId: string;
};

const MD_BODY =
  "[&_p]:mb-2 [&_p:last-child]:mb-0 [&_h1]:mb-1 [&_h1]:mt-2 [&_h1]:text-sm [&_h1]:font-semibold [&_h1]:first:mt-0 [&_h2]:mb-1 [&_h2]:mt-2 [&_h2]:text-xs [&_h2]:font-semibold [&_h3]:mb-1 [&_h3]:mt-1.5 [&_h3]:text-xs [&_h3]:font-semibold [&_ul]:my-1 [&_ul]:ml-4 [&_ul]:list-disc [&_ol]:my-1 [&_ol]:ml-4 [&_ol]:list-decimal [&_li]:my-0.5 [&_code]:rounded [&_code]:bg-muted/90 [&_code]:px-1 [&_code]:font-mono [&_code]:text-[11px] [&_pre]:my-2 [&_pre]:max-h-48 [&_pre]:overflow-x-auto [&_pre]:overflow-y-auto [&_pre]:rounded-md [&_pre]:border [&_pre]:border-border [&_pre]:bg-muted/40 [&_pre]:p-2 [&_pre]:text-[11px] [&_a]:text-primary [&_a]:underline [&_strong]:text-foreground [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-2 [&_blockquote]:text-muted-foreground [&_table]:my-2 [&_table]:w-full [&_table]:border-collapse [&_table]:text-left [&_table]:text-[11px] [&_th]:border [&_th]:border-border [&_th]:bg-muted/50 [&_th]:px-1.5 [&_th]:py-1 [&_td]:border [&_td]:border-border [&_td]:px-1.5 [&_td]:py-1";

function newSession(overrides?: Partial<Pick<ChatSession, "title" | "messages">>): ChatSession {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: overrides?.title ?? "New chat",
    updatedAt: now,
    messages: overrides?.messages ?? [GREETING],
    proposedPlans: [],
    planAnchorIndex: null,
    apiSessionId: crypto.randomUUID(),
  };
}

function migrateLegacyBundle(): ChatBundle | null {
  try {
    const savedMessages = localStorage.getItem(STORAGE_MESSAGES);
    if (!savedMessages) return null;
    const parsedMessages = JSON.parse(savedMessages) as ChatMessage[];
    const parsedPlans = localStorage.getItem(STORAGE_PLANS)
      ? (JSON.parse(localStorage.getItem(STORAGE_PLANS)!) as PlanResponse[])
      : [];
    const savedAnchor = localStorage.getItem(STORAGE_PLAN_ANCHOR);
    let planAnchorIndex: number | null = null;
    if (parsedPlans.length > 0 && savedAnchor !== null) {
      const anchor = Number.parseInt(savedAnchor, 10);
      if (!Number.isNaN(anchor) && anchor >= 0 && anchor < parsedMessages.length) {
        planAnchorIndex = anchor;
      } else {
        for (let i = parsedMessages.length - 1; i >= 0; i--) {
          const m = parsedMessages[i];
          if (m?.role === "assistant" && !m.content.startsWith("[Error contacting agent:")) {
            planAnchorIndex = i;
            break;
          }
        }
      }
    }
    const s = newSession({
      title: "Imported chat",
      messages: parsedMessages.length > 0 ? parsedMessages : [GREETING],
    });
    s.proposedPlans = parsedPlans;
    s.planAnchorIndex = planAnchorIndex;
    localStorage.removeItem(STORAGE_MESSAGES);
    localStorage.removeItem(STORAGE_PLANS);
    localStorage.removeItem(STORAGE_PLAN_ANCHOR);
    return { sessions: [s], activeSessionId: s.id };
  } catch {
    return null;
  }
}

function formatSessionTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}

function ChatMarkdown({ children }: { children: string }) {
  return (
    <div className={MD_BODY}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children: c }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
              {c}
            </a>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`min-w-0 max-w-[85%] rounded-md border border-border p-2 text-xs leading-relaxed ${
          isUser ? "bg-muted text-foreground" : "bg-card text-muted-foreground"
        }`}
      >
        <ChatMarkdown>{msg.content}</ChatMarkdown>
      </div>
    </div>
  );
}

function ThinkingIndicator({ hintIndex }: { hintIndex: number }) {
  const hint = THINKING_HINTS[hintIndex % THINKING_HINTS.length];
  return (
    <div className="flex justify-start">
      <div className="min-w-0 max-w-[85%] overflow-hidden rounded-md border border-border bg-muted/30">
        <div className="h-0.5 w-full overflow-hidden bg-muted/50">
          <div className="h-full w-2/5 bg-gradient-to-r from-transparent via-primary/60 to-transparent motion-safe:animate-agent-shimmer" />
        </div>
        <div className="flex flex-col gap-1.5 px-3 py-2">
          <div className="flex items-center gap-2 text-[11px] font-medium text-muted-foreground">
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/35 opacity-60" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary/80" />
            </span>
            <span>Thinking</span>
            <span className="font-mono text-foreground motion-safe:animate-pulse">···</span>
          </div>
          <p className="text-[10px] leading-snug text-muted-foreground/90 motion-safe:animate-pulse">
            {hint}
          </p>
        </div>
      </div>
    </div>
  );
}

function TypingBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-start">
      <div className="relative min-w-0 max-w-[85%] rounded-md border border-border bg-card p-2 text-xs leading-relaxed text-muted-foreground">
        {text.length > 0 ? <ChatMarkdown>{text}</ChatMarkdown> : null}
        <span
          className="ml-0.5 inline-block h-3.5 w-0.5 translate-y-0.5 bg-primary/70 motion-safe:animate-pulse"
          aria-hidden
        />
      </div>
    </div>
  );
}

type PlanCardProps = {
  plan: PlanResponse;
  globeShowsProposalPreview: boolean;
  onCancelGlobePreview: () => void;
  onShowGlobePreview: () => void;
  onApprove: () => void;
  onDeny: () => void;
};

function PlanCard({
  plan,
  globeShowsProposalPreview,
  onCancelGlobePreview,
  onShowGlobePreview,
  onApprove,
  onDeny,
}: PlanCardProps) {
  const { getSimInstant } = useSimClock();
  const [, setTick] = useState(0);
  const nonEci = plan.maneuvers.some((m) => String(m.frame).toUpperCase() !== "ECI");

  useEffect(() => {
    if (plan.maneuvers.length === 0) return;
    let id = 0;
    const loop = () => {
      setTick((n) => (n + 1) % 10_000);
      id = requestAnimationFrame(loop);
    };
    id = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(id);
  }, [plan.maneuvers.length]);

  if (plan.maneuvers.length === 0) return null;

  const simInstant = getSimInstant();
  const simMs = simInstant.getTime();
  const burnBeforeSim = planHasBurnBeforeSimInstant(plan, simInstant);
  const effectiveValidationPassed = plan.validation_passed && !burnBeforeSim;

  return (
    <div className="flex justify-start">
      <Card className="w-full max-w-[95%] border-border/60 shadow-md ring-1 ring-black/[0.03] dark:ring-white/[0.06]">
        <CardHeader className="space-y-0.5 p-3 pb-2">
          <CardTitle className="text-xs font-semibold tracking-tight">
            Proposed plan · {plan.sat_id} · {plan.maneuvers.length} burn
            {plan.maneuvers.length === 1 ? "" : "s"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 p-3 pt-0">
          <div className="space-y-2 rounded-md border border-border bg-background p-2 font-mono text-[11px] leading-relaxed">
            {plan.maneuvers.map((m, i) => {
              const { x, y, z } = m.delta_v_mps;
              const mag = Math.hypot(x, y, z);
              const burnMs = Date.parse(m.epoch_utc);
              const tminus =
                Number.isFinite(burnMs) ? formatTMinusSim(simMs, burnMs) : "T− — (invalid epoch)";
              return (
                <div
                  key={`${m.epoch_utc}-${i}`}
                  className={i > 0 ? "border-t border-border/60 pt-2" : ""}
                >
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Burn {i + 1} · {m.frame || "ECI"}
                  </div>
                  <div className="mt-1 space-y-0.5 text-[10px] text-muted-foreground">
                    <div>
                      <span className="text-foreground/80">When (UTC): </span>
                      <span className="text-foreground">{formatBurnUtcReadable(m.epoch_utc)}</span>
                    </div>
                    <div>
                      <span className="text-foreground/80">Clock: </span>
                      <span className="tabular-nums text-foreground">{tminus}</span>
                    </div>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-baseline justify-between gap-x-2 gap-y-0.5 text-[10px]">
                    <span className="uppercase tracking-wide text-muted-foreground">Δv (m/s)</span>
                    <span className="font-mono text-foreground">
                      [{x.toFixed(4)}, {y.toFixed(4)}, {z.toFixed(4)}]
                    </span>
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    ‖Δv‖ = <span className="tabular-nums text-foreground">{mag.toFixed(4)}</span> m/s
                  </div>
                </div>
              );
            })}
            <Separator className="my-2" />
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span>Plan total ‖Δv‖</span>
              <span className="tabular-nums text-foreground">{plan.total_delta_v_mps.toFixed(4)} m/s</span>
            </div>
            <Separator className="my-2" />
            <div className="text-[11px] text-muted-foreground">{plan.objective}</div>
          </div>
          {nonEci ? (
            <p className="text-[10px] text-amber-600">
              Globe supports ECI burns only. Re-express maneuvers in ECI before you can approve.
            </p>
          ) : (
            <p className="text-[10px] text-muted-foreground">
              Before <strong>Approve</strong>: only Δv arrows on the catalog orbit (no orbit change).{" "}
              <strong>Approve</strong> applies the burn in the preview propagator. Use{" "}
              <strong>Cancel preview</strong> to hide arrows; restore with <strong>Show burn preview</strong>.
            </p>
          )}
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1">
              {effectiveValidationPassed ? (
                <Badge variant="outline" className="font-mono text-[10px] text-green-400">
                  validation passed
                </Badge>
              ) : (
                <Badge variant="destructive" className="font-mono text-[10px]">
                  validation failed
                </Badge>
              )}
            </div>
            {plan.validation_passed && burnBeforeSim ? (
              <p className="text-[10px] text-amber-600">
                One or more burns are before the ops sim clock; they cannot be treated as valid to
                execute from this timeline.
              </p>
            ) : null}
          </div>
          {!nonEci && !globeShowsProposalPreview ? (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="h-7 w-full text-[10px]"
              disabled={!effectiveValidationPassed}
              onClick={onShowGlobePreview}
            >
              Show burn preview on globe
            </Button>
          ) : null}
          {!nonEci && globeShowsProposalPreview ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 w-full text-[10px]"
              onClick={onCancelGlobePreview}
            >
              Cancel burn preview (globe)
            </Button>
          ) : null}
          <div className="grid grid-cols-2 gap-2">
            <Button
              size="sm"
              type="button"
              variant="default"
              className="h-8 text-xs"
              disabled={nonEci || !effectiveValidationPassed}
              title="Apply burns in the preview propagator (orbit changes on the globe)."
              onClick={onApprove}
            >
              <CheckCircle2 className="mr-1 h-3.5 w-3.5" />
              Approve
            </Button>
            <Button
              size="sm"
              type="button"
              variant="outline"
              className="h-8 border-destructive/50 text-xs text-destructive hover:bg-destructive/10"
              title="Decline this proposal and remove the preview from the globe."
              onClick={onDeny}
            >
              <Ban className="mr-1 h-3.5 w-3.5" />
              Deny
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function AgentChat() {
  const { getSimInstant } = useSimClock();
  const {
    primarySatId,
    conjunctionHits,
    selectedConjunctionId,
    replaceSatSelection,
    maneuverPreviewConfig,
    setManeuverPreviewConfig,
    clearConjunctionHitsForOperator,
    setSelectedConjunctionId,
  } = useOpsShell();
  const selectedConjunction = useMemo(
    () => conjunctionHits.find((e) => e.id === selectedConjunctionId) ?? null,
    [conjunctionHits, selectedConjunctionId],
  );

  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [agentPhase, setAgentPhase] = useState<AgentPhase>("idle");
  const [typingVisible, setTypingVisible] = useState("");
  const [thinkingHintIdx, setThinkingHintIdx] = useState(0);
  const [proposedPlans, setProposedPlans] = useState<PlanResponse[]>([]);
  const [planAnchorIndex, setPlanAnchorIndex] = useState<number | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);

  const sessionId = useRef<string>("");
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingTargetRef = useRef("");
  const pendingPlansRef = useRef<PlanResponse[] | null>(null);
  const proposedPlansRef = useRef<PlanResponse[]>([]);
  const assistantInsertIndexRef = useRef<number>(0);
  /** Latest preview plan id — avoids stale closures on Cancel. */
  const maneuverPreviewPlanIdRef = useRef<string | null>(null);
  /** Plan ids the operator hid with Cancel; blocks the auto-preview effect from immediately re-applying. */
  const suppressedAutoPreviewPlanIdsRef = useRef<Set<string>>(new Set());

  proposedPlansRef.current = proposedPlans;
  maneuverPreviewPlanIdRef.current = maneuverPreviewConfig?.planId ?? null;

  const isBusy = agentPhase !== "idle";

  const sortedSessions = useMemo(
    () => [...sessions].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()),
    [sessions],
  );

  function applyTextareaHeight(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = `${Math.max(TEXTAREA_MIN_HEIGHT_PX, el.scrollHeight)}px`;
  }

  const persistBundle = useCallback((nextSessions: ChatSession[], nextActiveId: string) => {
    const bundle: ChatBundle = { sessions: nextSessions, activeSessionId: nextActiveId };
    localStorage.setItem(STORAGE_BUNDLE, JSON.stringify(bundle));
  }, []);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_BUNDLE);
    let bundle: ChatBundle;

    if (raw) {
      try {
        const parsed = JSON.parse(raw) as ChatBundle;
        if (!parsed.sessions?.length) throw new Error("empty");
        bundle = parsed;
      } catch {
        bundle = migrateLegacyBundle() ?? { sessions: [newSession()], activeSessionId: "" };
        if (!bundle.activeSessionId && bundle.sessions[0]) {
          bundle.activeSessionId = bundle.sessions[0].id;
        }
      }
    } else {
      bundle = migrateLegacyBundle() ?? { sessions: [newSession()], activeSessionId: "" };
      if (!bundle.activeSessionId && bundle.sessions[0]) {
        bundle.activeSessionId = bundle.sessions[0].id;
      }
    }

    let sessionsOut = bundle.sessions;
    let activeId = bundle.activeSessionId;
    let active = sessionsOut.find((s) => s.id === activeId) ?? sessionsOut[0];
    if (!active) {
      const s = newSession();
      sessionsOut = [s];
      activeId = s.id;
      active = s;
    }

    persistBundle(sessionsOut, active.id);

    setSessions(sessionsOut);
    setActiveSessionId(active.id);
    setMessages(active.messages);
    setProposedPlans(active.proposedPlans);
    setPlanAnchorIndex(active.planAnchorIndex);
    sessionId.current = active.apiSessionId;
    setHydrated(true);
  }, [persistBundle]);


  useEffect(() => {
    if (!hydrated || !activeSessionId) return;
    setSessions((prev) => {
      const idx = prev.findIndex((s) => s.id === activeSessionId);
      if (idx < 0) return prev;
      const next = [...prev];
      next[idx] = {
        ...next[idx],
        messages,
        proposedPlans,
        planAnchorIndex,
        updatedAt: new Date().toISOString(),
      };
      persistBundle(next, activeSessionId);
      return next;
    });
  }, [messages, proposedPlans, planAnchorIndex, activeSessionId, hydrated, persistBundle]);

  useEffect(() => {
    if (!hydrated) return;
    const firstUser = messages.find((m) => m.role === "user");
    if (!firstUser?.content.trim()) return;
    setSessions((prev) => {
      let changed = false;
      const next = prev.map((s) => {
        if (s.id !== activeSessionId || s.title !== "New chat") return s;
        const t = firstUser.content.trim().replace(/\s+/g, " ");
        const title = t.length > 40 ? `${t.slice(0, 40)}…` : t;
        changed = true;
        return { ...s, title };
      });
      if (changed) persistBundle(next, activeSessionId);
      return changed ? next : prev;
    });
  }, [messages, activeSessionId, hydrated, persistBundle]);

  useEffect(() => {
    if (agentPhase !== "thinking") return;
    const id = window.setInterval(() => {
      setThinkingHintIdx((i) => (i + 1) % THINKING_HINTS.length);
    }, 2400);
    return () => window.clearInterval(id);
  }, [agentPhase]);

  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, agentPhase, typingVisible, planAnchorIndex, proposedPlans]);

  useEffect(() => {
    if (agentPhase !== "typing") return;
    const full = typingTargetRef.current;
    if (!full.length) {
      setAgentPhase("idle");
      return;
    }

    let cancelled = false;
    let i = 0;
    let raf = 0;
    const charsPerStep = () => Math.max(1, Math.ceil(full.length / 100));

    const step = () => {
      if (cancelled) return;
      i = Math.min(i + charsPerStep(), full.length);
      setTypingVisible(full.slice(0, i));
      if (i < full.length) {
        raf = window.requestAnimationFrame(step);
      } else {
        if (cancelled) return;
        const insertAt = assistantInsertIndexRef.current;
        const plans = pendingPlansRef.current;
        pendingPlansRef.current = null;

        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.content === full) {
            return prev;
          }
          return [...prev, { role: "assistant", content: full }];
        });

        if (plans && plans.length > 0) {
          setProposedPlans((prev) => mergeProposedPlans(prev, plans));
          setPlanAnchorIndex(insertAt);
        }

        setTypingVisible("");
        setAgentPhase("idle");
      }
    };

    raf = window.requestAnimationFrame(step);
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(raf);
    };
  }, [agentPhase]);

  useEffect(() => {
    const el = textareaRef.current;
    if (el && hydrated) {
      applyTextareaHeight(el);
    }
  }, [hydrated, input]);

  const startNewChat = useCallback(() => {
    if (isBusy) return;
    const s = newSession();
    setSessions((prev) => {
      const next = [s, ...prev].slice(0, MAX_SESSIONS);
      persistBundle(next, s.id);
      return next;
    });
    setActiveSessionId(s.id);
    setMessages([GREETING]);
    setProposedPlans([]);
    setPlanAnchorIndex(null);
    sessionId.current = s.apiSessionId;
    setInput("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      applyTextareaHeight(textareaRef.current);
    }
  }, [isBusy, persistBundle]);

  const switchToSession = useCallback(
    (s: ChatSession) => {
      if (isBusy || s.id === activeSessionId) return;
      setActiveSessionId(s.id);
      setMessages(s.messages);
      setProposedPlans(s.proposedPlans);
      setPlanAnchorIndex(s.planAnchorIndex);
      sessionId.current = s.apiSessionId;
      setInput("");
      setHistoryOpen(false);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        applyTextareaHeight(textareaRef.current);
      }
      setSessions((prev) => {
        persistBundle(prev, s.id);
        return prev;
      });
    },
    [isBusy, activeSessionId, persistBundle],
  );

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    applyTextareaHeight(e.target);
  }

  const submitUserMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || agentPhase !== "idle") return;

      const userMsg: ChatMessage = { role: "user", content: text };
      const nextMessages = [...messages, userMsg];
      setMessages(nextMessages);
      setInput("");
      setThinkingHintIdx(0);

      assistantInsertIndexRef.current = nextMessages.length;

      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        applyTextareaHeight(textareaRef.current);
      }

      setAgentPhase("thinking");

      try {
        const burnCoversSelected =
          maneuverPreviewConfig?.burnApplied === true &&
          selectedConjunction != null &&
          (selectedConjunction.primary_sat_id === maneuverPreviewConfig.satId ||
            selectedConjunction.secondary_sat_id === maneuverPreviewConfig.satId);

        const conjunction_context =
          burnCoversSelected || selectedConjunction == null
            ? undefined
            : {
                conjunction_id: selectedConjunction.id,
                primary_sat_id: selectedConjunction.primary_sat_id,
                secondary_sat_id: selectedConjunction.secondary_sat_id,
                tca_utc: selectedConjunction.tca_utc,
                miss_distance_km: selectedConjunction.miss_distance_km,
                pc_heuristic: selectedConjunction.pc_heuristic,
                source: "CATALOG_SCREEN",
              };

        const res: AgentTurnResponse = await postAgentTurn({
          session_id: sessionId.current,
          operator_id: OPERATOR_ID,
          messages: nextMessages,
          ...(primarySatId ? { focus_sat_id: primarySatId } : {}),
          ...(conjunction_context ? { conjunction_context } : {}),
        });
        pendingPlansRef.current = res.proposed_plans.length > 0 ? res.proposed_plans : null;
        typingTargetRef.current = res.assistant_message;
        setTypingVisible("");
        setAgentPhase("typing");
      } catch (err) {
        const base = getApiBaseUrl();
        let msg =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : "Unknown error";
        if (
          err instanceof TypeError ||
          (typeof msg === "string" && /failed to fetch/i.test(msg))
        ) {
          msg = `Cannot reach the API at ${base}. Start uvicorn in apps/api (port 8000) and set NEXT_PUBLIC_API_BASE_URL in apps/web/.env.local if needed.`;
        }
        setMessages((prev) => [...prev, { role: "assistant", content: `[Error contacting agent: ${msg}]` }]);
        pendingPlansRef.current = null;
        setAgentPhase("idle");
      }
    },
    [agentPhase, messages, maneuverPreviewConfig, primarySatId, selectedConjunction],
  );

  const handleSend = useCallback(() => {
    void submitUserMessage(input);
  }, [input, submitUserMessage]);

  const applyPlanPreview = useCallback(
    (p: PlanResponse, opts?: { burnApplied?: boolean }) => {
      const burnApplied = opts?.burnApplied ?? true;
      replaceSatSelection([p.sat_id]);
      const maneuvers = p.maneuvers.map((m) => ({
        epoch_utc: m.epoch_utc,
        delta_v_mps: { ...m.delta_v_mps },
        frame: m.frame || "ECI",
      }));
      const anchorUtcMs = getSimInstant().getTime();
      setManeuverPreviewConfig({
        planId: p.plan_id,
        satId: p.sat_id,
        maneuvers,
        timelineWindowMs: computeManeuverTimelineWindowMs(anchorUtcMs, maneuvers),
        burnApplied,
        ...(burnApplied ? { trajectoryPreviewAnchorUtc: new Date(anchorUtcMs).toISOString() } : {}),
      });
    },
    [getSimInstant, replaceSatSelection, setManeuverPreviewConfig],
  );

  const firstProposalKey = useMemo(() => {
    const p = proposedPlans[0];
    if (!p) return "";
    return `${p.plan_id}|${p.sat_id}|${p.maneuvers.map((m) => `${m.epoch_utc}:${m.delta_v_mps.x},${m.delta_v_mps.y},${m.delta_v_mps.z}`).join("|")}`;
  }, [proposedPlans]);

  /** Proposal: nominal orbit + Δv arrows only (``burnApplied: false``) until Approve or cancel. */
  useEffect(() => {
    if (!firstProposalKey) return;
    if (maneuverPreviewConfig?.burnApplied === true) return;
    const plans = proposedPlansRef.current;
    const p = plans[0];
    if (!p) return;
    for (const id of [...suppressedAutoPreviewPlanIdsRef.current]) {
      if (!plans.some((pl) => pl.plan_id === id)) suppressedAutoPreviewPlanIdsRef.current.delete(id);
    }
    if (suppressedAutoPreviewPlanIdsRef.current.has(p.plan_id)) return;
    if (p.maneuvers.some((m) => String(m.frame).toUpperCase() !== "ECI")) return;
    if (!p.validation_passed || planHasBurnBeforeSimInstant(p, getSimInstant())) return;
    applyPlanPreview(p, { burnApplied: false });
  }, [
    applyPlanPreview,
    firstProposalKey,
    getSimInstant,
    maneuverPreviewConfig?.burnApplied,
  ]);

  const handlePlanApprove = useCallback(
    (p: PlanResponse) => {
      if (!p.validation_passed || planHasBurnBeforeSimInstant(p, getSimInstant())) return;
      clearConjunctionHitsForOperator();
      setSelectedConjunctionId(null);
      const nonEci = p.maneuvers.some((m) => String(m.frame).toUpperCase() !== "ECI");
      if (!nonEci) {
        applyPlanPreview(p, { burnApplied: true });
      }
      setProposedPlans((prev) => {
        const next = prev.filter((x) => x.plan_id !== p.plan_id);
        if (next.length === 0) setPlanAnchorIndex(null);
        return next;
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            `**Operator approved** plan \`${p.plan_id}\` for **${p.sat_id}** (total ‖Δv‖ ${p.total_delta_v_mps.toFixed(2)} m/s). ` +
            "The globe now uses the **propagated** maneuver preview (catalog TLE + applied Δv in the preview model). " +
            "This UI does not command the spacecraft.",
        },
      ]);
    },
    [applyPlanPreview, clearConjunctionHitsForOperator, getSimInstant, setSelectedConjunctionId],
  );

  const handlePlanDeny = useCallback(
    (p: PlanResponse) => {
      setSelectedConjunctionId(null);
      if (maneuverPreviewConfig?.planId === p.plan_id) {
        setManeuverPreviewConfig(null);
      }
      setProposedPlans((prev) => {
        const next = prev.filter((x) => x.plan_id !== p.plan_id);
        if (next.length === 0) setPlanAnchorIndex(null);
        return next;
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `**Operator declined** plan \`${p.plan_id}\` for **${p.sat_id}**. Ask the agent for another option if you need one.`,
        },
      ]);
    },
    [maneuverPreviewConfig?.planId, setManeuverPreviewConfig, setSelectedConjunctionId],
  );

  const globeShowsProposalFor = useCallback(
    (p: PlanResponse) => {
      const c = maneuverPreviewConfig;
      if (!c || c.burnApplied || c.planId !== p.plan_id) return false;
      return true;
    },
    [maneuverPreviewConfig],
  );

  const handleCancelGlobePreviewFor = useCallback(
    (p: PlanResponse) => {
      if (maneuverPreviewPlanIdRef.current === p.plan_id) {
        suppressedAutoPreviewPlanIdsRef.current.add(p.plan_id);
        setManeuverPreviewConfig(null);
      }
    },
    [setManeuverPreviewConfig],
  );

  const handleShowGlobePreviewFor = useCallback(
    (p: PlanResponse) => {
      if (!p.validation_passed || planHasBurnBeforeSimInstant(p, getSimInstant())) return;
      if (p.maneuvers.some((m) => String(m.frame).toUpperCase() !== "ECI")) return;
      suppressedAutoPreviewPlanIdsRef.current.delete(p.plan_id);
      applyPlanPreview(p, { burnApplied: false });
    },
    [applyPlanPreview, getSimInstant],
  );

  useEffect(() => {
    const onDraft = (ev: Event) => {
      const ce = ev as CustomEvent<{ text?: string }>;
      const t = ce.detail?.text;
      if (typeof t !== "string" || !t.trim()) return;
      void submitUserMessage(t);
    };
    window.addEventListener("node-agent-set-draft", onDraft as EventListener);
    return () => window.removeEventListener("node-agent-set-draft", onDraft as EventListener);
  }, [submitUserMessage]);

  return (
    <aside className="flex h-full min-h-0 w-full min-w-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border/50 bg-muted/10 px-3 py-2.5">
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <span className="shrink-0 text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground/90">
            Agent
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
            title="Past chats"
            aria-label="Open chat history"
            onClick={() => setHistoryOpen(true)}
          >
            <History className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
            title="New chat"
            aria-label="Start new chat"
            disabled={isBusy}
            onClick={() => startNewChat()}
          >
            <MessageSquarePlus className="h-3.5 w-3.5" />
          </Button>
        </div>
        <Badge
          variant="outline"
          className="shrink-0 border-emerald-500/30 bg-emerald-500/10 font-mono text-[10px] text-emerald-700 dark:text-emerald-400/90"
        >
          live
        </Badge>
      </div>
      <Separator className="opacity-50" />
      <div
        ref={chatScrollRef}
        className="h-0 min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-3 py-3"
      >
        <div className="space-y-3">
          {messages.map((msg, i) => (
            <div key={`${i}-${msg.role}-${msg.content.slice(0, 12)}`} className="space-y-3">
              <MessageBubble msg={msg} />
              {planAnchorIndex === i && agentPhase !== "typing" && proposedPlans.length > 0
                ? proposedPlans.map((pl) => (
                    <PlanCard
                      key={pl.plan_id}
                      plan={pl}
                      globeShowsProposalPreview={globeShowsProposalFor(pl)}
                      onCancelGlobePreview={() => handleCancelGlobePreviewFor(pl)}
                      onShowGlobePreview={() => handleShowGlobePreviewFor(pl)}
                      onApprove={() => handlePlanApprove(pl)}
                      onDeny={() => handlePlanDeny(pl)}
                    />
                  ))
                : null}
            </div>
          ))}
          {agentPhase === "thinking" && <ThinkingIndicator hintIndex={thinkingHintIdx} />}
          {agentPhase === "typing" && <TypingBubble text={typingVisible} />}
        </div>
      </div>
      <Separator className="opacity-50" />
      <div className="border-t border-border/40 bg-muted/5 p-3">
        <textarea
          ref={textareaRef}
          rows={2}
          placeholder="Enter to send  ·  Shift+Enter for newline"
          className="w-full resize-none overflow-y-auto rounded-lg border border-border/60 bg-background/80 px-3 py-2 font-mono text-xs leading-[15px] text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50"
          style={{ minHeight: TEXTAREA_MIN_HEIGHT_PX, maxHeight: 160 }}
          value={input}
          disabled={isBusy}
          onChange={handleInputChange}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
        />
        {isBusy && (
          <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin shrink-0" />
            <span>{agentPhase === "thinking" ? "Working…" : "Writing response…"}</span>
          </div>
        )}
      </div>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-h-[min(560px,85vh)] gap-0 overflow-hidden p-0 sm:max-w-md">
          <DialogHeader className="border-b border-border px-4 py-3 text-left">
            <DialogTitle className="text-sm">Past chats</DialogTitle>
            <DialogDescription className="text-xs">
              Open a previous thread. Each chat keeps its own context for the agent API.
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[min(420px,60vh)]">
            <div className="flex flex-col p-1">
              {sortedSessions.length === 0 ? (
                <p className="px-3 py-6 text-center text-xs text-muted-foreground">No saved chats yet.</p>
              ) : (
                sortedSessions.map((s) => {
                  const isCurrent = s.id === activeSessionId;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      className={`flex w-full flex-col items-start gap-0.5 rounded-md px-3 py-2.5 text-left text-xs transition-colors hover:bg-muted ${
                        isCurrent ? "bg-muted/60" : ""
                      }`}
                      onClick={() => switchToSession(s)}
                    >
                      <span className="line-clamp-2 w-full font-medium text-foreground">{s.title}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {formatSessionTime(s.updatedAt)}
                        {isCurrent ? " · current" : ""}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
