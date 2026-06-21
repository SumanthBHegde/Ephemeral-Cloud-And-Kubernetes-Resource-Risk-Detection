import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Bot, Send, Sparkles, ShieldAlert } from "lucide-react";
import { useData } from "../lib/data";
import { PageState } from "../components/shared";
import { Card, Badge, Button } from "../components/ui";
import { bandToLevel, cn } from "../lib/utils";
import { SeverityBadge } from "../components/ui";

export default function Chat() {
  const { data, loading, error } = useData();
  return (
    <PageState loading={loading} error={error}>
      {data && <ChatBody incidents={data.incidents} />}
    </PageState>
  );
}

/* Build a canned assistant answer about an incident from its triage narrative. */
function narrate(inc) {
  if (!inc) return null;
  if (!inc.likely_intent) {
    return {
      text: `**${inc.incident_id}** is a LOW-band incident (fused risk ${inc.risk_score.toFixed(3)}). It was suppressed below the triage threshold, so no LLM narrative was generated. It groups ${inc.event_count} events with ${inc.tripwire_hits} tripwire hits.`,
      inc,
    };
  }
  const ev = (inc.key_evidence || []).map((e) => `- ${e}`).join("\n");
  const gr = (inc.recommended_guardrails || []).map((g) => `- ${g}`).join("\n");
  return {
    text:
      `**${inc.incident_id}** — ${inc.risk_band} (confidence ${Math.round((inc.confidence || 0) * 100)}%).\n\n` +
      `**Likely intent:** ${inc.likely_intent}\n\n` +
      (inc.disambiguation ? `**Why not benign:** ${inc.disambiguation}\n\n` : "") +
      `**MITRE:** ${(inc.mitre || []).join(", ")}\n\n` +
      `**Key evidence:**\n${ev}\n\n` +
      `**Recommended guardrails:**\n${gr}`,
    inc,
  };
}

/* very small markdown-ish renderer: **bold** + newlines */
function RichText({ text }) {
  return (
    <div className="space-y-1 text-sm leading-relaxed">
      {text.split("\n").map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1" />;
        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        return (
          <p key={i}>
            {parts.map((p, j) =>
              p.startsWith("**") && p.endsWith("**")
                ? <strong key={j}>{p.slice(2, -2)}</strong>
                : <span key={j}>{p}</span>
            )}
          </p>
        );
      })}
    </div>
  );
}

function ChatBody({ incidents }) {
  const [params] = useSearchParams();
  const byId = Object.fromEntries(incidents.map((i) => [i.incident_id, i]));
  const topTriaged = incidents.filter((i) => i.likely_intent).slice(0, 6);

  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "I'm your AI Risk Analyst. Ask me about any correlated incident, or pick a finding below and I'll explain the triage — likely intent, MITRE techniques, evidence, and guardrails.",
    },
  ]);
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);

  // preseed from ?incident= (deep link from the Risk Findings drawer)
  useEffect(() => {
    const id = params.get("incident");
    if (id && byId[id]) {
      const n = narrate(byId[id]);
      setMessages((m) => [
        ...m,
        { role: "user", text: `Explain incident ${id}.` },
        { role: "assistant", text: n.text, citation: byId[id] },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  function answer(text) {
    // match an incident id mentioned, else the highest-risk triaged incident
    const idMatch = text.match(/INC-\d+/i);
    let inc = idMatch ? byId[idMatch[0].toUpperCase()] : null;
    if (!inc) inc = incidents.find((i) => i.likely_intent) || incidents[0];
    return narrate(inc);
  }

  function send(text) {
    const t = (text ?? input).trim();
    if (!t) return;
    const n = answer(t);
    setMessages((m) => [...m, { role: "user", text: t }, { role: "assistant", text: n.text, citation: n.inc }]);
    setInput("");
  }

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-btn bg-primary/10 text-primary"><Bot className="h-5 w-5" /></div>
        <div>
          <h1 className="text-lg font-bold tracking-tight">AI Risk Analyst</h1>
          <p className="text-xs text-muted-foreground">Grounded in Stage-5 triage narratives · offline / cached</p>
        </div>
        <Badge variant="success" className="ml-auto"><span className="h-1.5 w-1.5 rounded-full bg-success" /> gpt-4o-mini (cached)</Badge>
      </div>

      <Card className="flex min-h-0 flex-1 flex-col">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto scrollbar-thin p-4">
          {messages.map((m, i) => (
            <div key={i} className={cn("flex", m.role === "user" ? "justify-end" : "justify-start")}>
              <div className={cn("max-w-[85%] rounded-card px-3.5 py-2.5",
                m.role === "user" ? "bg-primary text-primary-foreground" : "border border-border bg-card")}>
                <RichText text={m.text} />
                {m.citation && (
                  <button
                    onClick={() => (window.location.href = `/app/findings?incident=${m.citation.incident_id}`)}
                    className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2 py-0.5 text-xs hover:border-ring"
                  >
                    <ShieldAlert className="h-3 w-3" />
                    <span className="font-mono">{m.citation.incident_id}</span>
                    <SeverityBadge level={bandToLevel(m.citation.risk_band)} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* suggested prompts */}
        <div className="flex flex-wrap gap-2 border-t border-border p-3">
          {topTriaged.map((i) => (
            <button
              key={i.incident_id}
              onClick={() => send(`Explain incident ${i.incident_id}.`)}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 text-xs hover:border-ring"
            >
              <Sparkles className="h-3 w-3 text-primary" /> {i.incident_id}
            </button>
          ))}
        </div>

        {/* composer */}
        <div className="flex items-center gap-2 border-t border-border p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about an incident, e.g. 'Explain INC-0515'…"
            className="h-10 flex-1 rounded-btn border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <Button onClick={() => send()} className="h-10"><Send className="h-4 w-4" /></Button>
        </div>
      </Card>
    </div>
  );
}
