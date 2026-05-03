"use client";

import { History, Loader2, MessageSquarePlus, ShieldCheck } from "lucide-react";
import Link from "next/link";
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
import { postAgentTurn } from "@/lib/api";
import type { AgentTurnResponse, ChatMessage, PlanResponse } from "@/lib/types";

const OPERATOR_ID = "demo";
const FOCUS_SAT = "EO-12";

/** v2 bundle — multiple sessions */
const STORAGE_BUNDLE = "node-agent-chat-v2";
/** legacy single-thread keys (migrated once) */
const STORAGE_MESSAGES = "node-agent-messages";
const STORAGE_PLANS = "node-agent-plans";
const STORAGE_PLAN_ANCHOR = "node-agent-plan-anchor";

const MAX_SESSIONS = 40;

/** text-xs ~15px line + py-2 (8px×2) — minimum two visible lines. */
const TEXTAREA_LINE_PX = 15;
const TEXTAREA_PAD_Y_PX = 16;
const TEXTAREA_MIN_LINES = 2;
const TEXTAREA_MIN_HEIGHT_PX = TEXTAREA_LINE_PX * TEXTAREA_MIN_LINES + TEXTAREA_PAD_Y_PX;

const GREETING: ChatMessage = {
  role: "assistant",
  content:
    "I'm monitoring your constellation. EO-12 has one active conjunction above your mitigation threshold — type \"tell me about CJX-2041\" to start.",
};

const THINKING_HINTS = [
  "Reviewing your request…",
  "Checking mock conjunctions and satellite state…",
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

function PlanCard({ plan }: { plan: PlanResponse }) {
  const burn = plan.maneuvers[0];
  if (!burn) return null;
  const { x, y, z } = burn.delta_v_mps;

  return (
    <div className="flex justify-start">
      <Card className="w-full max-w-[95%]">
        <CardHeader className="p-3 pb-2">
          <CardTitle className="text-xs">Proposed maneuver · {plan.sat_id}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 p-3 pt-0">
          <div className="rounded-md border border-border bg-background p-2 font-mono text-[11px] leading-relaxed">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
              <span>Δv ({burn.frame}, m/s)</span>
              <span className="font-mono text-foreground">
                [{x.toFixed(3)}, {y.toFixed(3)}, {z.toFixed(3)}]
              </span>
            </div>
            <Separator className="my-2" />
            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
              <span>Total ‖Δv‖</span>
              <span className="text-foreground">{plan.total_delta_v_mps.toFixed(4)} m/s</span>
            </div>
            <Separator className="my-2" />
            <div className="text-[11px] text-muted-foreground">{plan.objective}</div>
          </div>
          <div className="flex items-center gap-1">
            {plan.validation_passed ? (
              <Badge variant="outline" className="font-mono text-[10px] text-green-400">
                validation passed
              </Badge>
            ) : (
              <Badge variant="destructive" className="font-mono text-[10px]">
                validation failed
              </Badge>
            )}
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button size="sm" variant="secondary" type="button" className="h-8 text-xs" asChild>
              <Link href={`/planner/${plan.sat_id}`}>Edit in planner</Link>
            </Button>
            <Button
              size="sm"
              type="button"
              className="h-8 text-xs"
              onClick={() => console.log("Approve plan:", plan.plan_id)}
            >
              <ShieldCheck className="mr-1 h-3.5 w-3.5" />
              Approve
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export function AgentChat() {
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
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingTargetRef = useRef("");
  const pendingPlansRef = useRef<PlanResponse[] | null>(null);
  const assistantInsertIndexRef = useRef<number>(0);

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
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" });
    }
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
          setProposedPlans(plans);
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

  async function handleSend() {
    const text = input.trim();
    if (!text || isBusy) return;

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
      const res: AgentTurnResponse = await postAgentTurn({
        session_id: sessionId.current,
        operator_id: OPERATOR_ID,
        messages: nextMessages,
        focus_sat_id: FOCUS_SAT,
      });
      pendingPlansRef.current = res.proposed_plans.length > 0 ? res.proposed_plans : null;
      typingTargetRef.current = res.assistant_message;
      setTypingVisible("");
      setAgentPhase("typing");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setMessages((prev) => [...prev, { role: "assistant", content: `[Error contacting agent: ${msg}]` }]);
      pendingPlansRef.current = null;
      setAgentPhase("idle");
    }
  }

  const plan = proposedPlans[0];

  return (
    <aside className="flex min-h-0 w-full min-w-0 flex-col border-l border-border bg-background/60">
      <div className="flex items-center justify-between gap-2 px-3 py-2">
        <div className="flex min-w-0 flex-1 items-center gap-1">
          <span className="shrink-0 text-xs font-semibold tracking-wide text-muted-foreground">AGENT</span>
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
        <Badge variant="outline" className="shrink-0 font-mono text-[10px]">
          live
        </Badge>
      </div>
      <Separator />
      <ScrollArea className="min-h-0 flex-1 px-3 py-3">
        <div className="space-y-3">
          {messages.map((msg, i) => (
            <div key={`${i}-${msg.role}-${msg.content.slice(0, 12)}`} className="space-y-3">
              <MessageBubble msg={msg} />
              {plan && planAnchorIndex === i && agentPhase !== "typing" ? <PlanCard plan={plan} /> : null}
            </div>
          ))}
          {agentPhase === "thinking" && <ThinkingIndicator hintIndex={thinkingHintIdx} />}
          {agentPhase === "typing" && <TypingBubble text={typingVisible} />}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>
      <Separator />
      <div className="p-3">
        <textarea
          ref={textareaRef}
          rows={2}
          placeholder="Message the agent  ·  Enter to send  ·  Shift+Enter for newline"
          className="w-full resize-none overflow-y-auto rounded-md border border-input bg-transparent px-3 py-2 font-mono text-xs leading-[15px] text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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
