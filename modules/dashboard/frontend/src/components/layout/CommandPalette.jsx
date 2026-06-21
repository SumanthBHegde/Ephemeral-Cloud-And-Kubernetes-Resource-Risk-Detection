import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Search, LayoutDashboard, ShieldAlert, Boxes, BarChart3, Bot,
  FileText, Bell, Settings, CornerDownLeft, ArrowUp, ArrowDown, Server,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useData } from "../../lib/data";

const pages = [
  { label: "Dashboard", to: "/app", icon: LayoutDashboard, group: "Navigate" },
  { label: "Risk Findings", to: "/app/findings", icon: ShieldAlert, group: "Navigate" },
  { label: "Resource Explorer", to: "/app/resources", icon: Boxes, group: "Navigate" },
  { label: "Analytics", to: "/app/analytics", icon: BarChart3, group: "Navigate" },
  { label: "AI Risk Analyst", to: "/app/chat", icon: Bot, group: "Navigate" },
  { label: "Reports", to: "/app/reports", icon: FileText, group: "Navigate" },
  { label: "Notifications", to: "/app/notifications", icon: Bell, group: "Navigate" },
  { label: "Settings", to: "/app/settings", icon: Settings, group: "Navigate" },
];

export default function CommandPalette({ open, onClose }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const navigate = useNavigate();
  const { data } = useData();

  useEffect(() => { if (open) { setQ(""); setActive(0); } }, [open]);

  if (!open) return null;

  const incidents = data?.incidents || [];
  const events = data?.events || [];
  const ql = q.toLowerCase();

  const navResults = pages
    .filter((p) => p.label.toLowerCase().includes(ql))
    .map((p) => ({ ...p, action: () => navigate(p.to) }));

  const findingResults = incidents
    .filter((i) => !ql || i.incident_id.toLowerCase().includes(ql) || (i.likely_intent || "").toLowerCase().includes(ql))
    .slice(0, 5)
    .map((i) => ({
      label: i.likely_intent || `${i.event_count} correlated events`,
      sub: i.incident_id, icon: ShieldAlert, group: "Findings",
      action: () => navigate(`/app/findings?incident=${i.incident_id}`),
    }));

  const resourceResults = ql
    ? events
        .filter((e) => (e.resource_id || "").toLowerCase().includes(ql) || (e.principal_id || "").toLowerCase().includes(ql))
        .slice(0, 5)
        .map((e) => ({
          label: e.resource_id || e.principal_id, sub: e.cohort, icon: Server, group: "Resources",
          action: () => navigate("/app/resources"),
        }))
    : [];

  const all = [...navResults, ...findingResults, ...resourceResults];
  const run = (i) => { all[i]?.action?.(); onClose(); };

  const onKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, all.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === "Enter") { e.preventDefault(); run(active); }
    if (e.key === "Escape") onClose();
  };

  let groupSeen = {};

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center p-4 pt-[12vh]">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative z-10 w-full max-w-xl overflow-hidden rounded-dialog border border-border bg-popover shadow-lg animate-fade-in">
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            autoFocus
            value={q}
            onChange={(e) => { setQ(e.target.value); setActive(0); }}
            onKeyDown={onKey}
            placeholder="Search findings, resources, pages…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto scrollbar-thin p-2">
          {all.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">No results for "{q}"</div>}
          {all.map((r, i) => {
            const showGroup = !groupSeen[r.group];
            groupSeen[r.group] = true;
            return (
              <div key={i}>
                {showGroup && <div className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">{r.group}</div>}
                <button
                  onMouseEnter={() => setActive(i)}
                  onClick={() => run(i)}
                  className={cn("flex w-full items-center gap-3 rounded-btn px-2.5 py-2 text-left text-sm", active === i ? "bg-primary/10 text-primary" : "hover:bg-muted")}
                >
                  <r.icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1 truncate">{r.label}</span>
                  {r.sub && <span className="font-mono text-xs text-muted-foreground">{r.sub}</span>}
                </button>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1"><ArrowUp className="h-3 w-3" /><ArrowDown className="h-3 w-3" /> navigate</span>
          <span className="flex items-center gap-1"><CornerDownLeft className="h-3 w-3" /> select</span>
        </div>
      </div>
    </div>
  );
}
