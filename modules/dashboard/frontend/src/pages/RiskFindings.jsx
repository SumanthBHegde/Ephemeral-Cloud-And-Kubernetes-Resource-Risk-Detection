import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  LayoutGrid, List, X, ShieldAlert, Bot, Clock, Boxes, Users, Server,
  GitBranch, Activity, ArrowRight, Camera,
} from "lucide-react";
import { useData } from "../lib/data";
import { PageHeader, EmptyState, PageState } from "../components/shared";
import {
  Button, Card, Badge, SeverityBadge, SearchInput, Select, Progress, Tabs, TabsList, TabsTrigger,
} from "../components/ui";
import { bandToLevel, fmtTime, fmtDuration, fmtPct, cn } from "../lib/utils";

const BANDS = ["ALL", "CRITICAL", "HIGH", "LOW"];

export default function RiskFindings() {
  const { data, loading, error } = useData();
  return (
    <PageState loading={loading} error={error}>
      {data && <FindingsBody data={data} />}
    </PageState>
  );
}

function FindingsBody({ data }) {
  const incidents = data.incidents;
  const [params, setParams] = useSearchParams();
  const [view, setView] = useState("grid");
  const [q, setQ] = useState("");
  const [band, setBand] = useState("ALL");
  const [cohort, setCohort] = useState("ALL");

  const selectedId = params.get("incident");
  const selected = useMemo(
    () => incidents.find((i) => i.incident_id === selectedId) || null,
    [incidents, selectedId]
  );
  const open = (id) => setParams(id ? { incident: id } : {});

  const cohorts = useMemo(() => {
    const s = new Set();
    incidents.forEach((i) => i.top_events.forEach((e) => e.cohort && s.add(e.cohort)));
    return ["ALL", ...[...s].sort()];
  }, [incidents]);

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return incidents.filter((i) => {
      if (band !== "ALL" && i.risk_band !== band) return false;
      if (cohort !== "ALL" && !i.top_events.some((e) => e.cohort === cohort)) return false;
      if (ql && !i.incident_id.toLowerCase().includes(ql) &&
          !(i.likely_intent || "").toLowerCase().includes(ql) &&
          !i.principal_ids.join(" ").toLowerCase().includes(ql)) return false;
      return true;
    });
  }, [incidents, q, band, cohort]);

  return (
    <div>
      <PageHeader
        title="Risk Findings"
        description="Correlated incidents ranked by fused risk score, with LLM triage."
        breadcrumb={["Console", "Risk Findings"]}
      >
        <Tabs value={view} onValueChange={setView}>
          <TabsList>
            <TabsTrigger value="grid"><LayoutGrid className="h-4 w-4" /></TabsTrigger>
            <TabsTrigger value="list"><List className="h-4 w-4" /></TabsTrigger>
          </TabsList>
        </Tabs>
      </PageHeader>

      <Card className="mb-4 p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <SearchInput
            className="sm:max-w-xs"
            placeholder="Search incidents, intent, principal…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Select value={band} onChange={(e) => setBand(e.target.value)} className="sm:w-40">
            {BANDS.map((b) => <option key={b} value={b}>{b === "ALL" ? "All risk bands" : b}</option>)}
          </Select>
          <Select value={cohort} onChange={(e) => setCohort(e.target.value)} className="sm:w-44">
            {cohorts.map((c) => <option key={c} value={c}>{c === "ALL" ? "All cohorts" : c}</option>)}
          </Select>
          <div className="flex items-center gap-3 sm:ml-auto">
            {(q || band !== "ALL" || cohort !== "ALL") && (
              <Button variant="ghost" size="sm" onClick={() => { setQ(""); setBand("ALL"); setCohort("ALL"); }}>Clear</Button>
            )}
            <span className="text-sm text-muted-foreground">{filtered.length} findings</span>
          </div>
        </div>
      </Card>

      {filtered.length === 0 ? (
        <EmptyState icon={ShieldAlert} title="No findings match" description="Adjust your filters to see more incidents." />
      ) : view === "grid" ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {filtered.map((i) => <FindingCard key={i.incident_id} inc={i} onClick={() => open(i.incident_id)} />)}
        </div>
      ) : (
        <Card className="divide-y divide-border">
          {filtered.map((i) => <FindingRow key={i.incident_id} inc={i} onClick={() => open(i.incident_id)} />)}
        </Card>
      )}

      {selected && <FindingDrawer inc={selected} onClose={() => open(null)} />}
    </div>
  );
}

function FindingCard({ inc, onClick }) {
  return (
    <button onClick={onClick} className="group text-left">
      <Card className="h-full p-4 transition-all hover:border-ring hover:shadow-md">
        <div className="mb-2 flex items-center justify-between">
          <SeverityBadge level={bandToLevel(inc.risk_band)} />
          <span className="text-xs text-muted-foreground">#{inc.risk_rank}</span>
        </div>
        <div className="mb-1 line-clamp-2 text-sm font-semibold leading-snug">
          {inc.likely_intent || `${inc.event_count} correlated events`}
        </div>
        <div className="mb-3 font-mono text-xs text-muted-foreground">{inc.incident_id}</div>
        <div className="flex flex-wrap gap-1.5">
          {(inc.mitre || []).slice(0, 3).map((m) => <Badge key={m} variant="outline" className="font-mono">{m}</Badge>)}
        </div>
        <div className="mt-3 flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1"><Activity className="h-3.5 w-3.5" /> {inc.event_count}</span>
          <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {fmtDuration(inc.window_s)}</span>
          <span className="ml-auto">risk {inc.risk_score.toFixed(2)}</span>
        </div>
      </Card>
    </button>
  );
}

function FindingRow({ inc, onClick }) {
  return (
    <button onClick={onClick} className="flex w-full items-center gap-4 p-3 text-left hover:bg-muted">
      <SeverityBadge level={bandToLevel(inc.risk_band)} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{inc.likely_intent || `${inc.event_count} correlated events`}</div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="font-mono">{inc.incident_id}</span><span>·</span>
          <span>{inc.event_count} events</span><span>·</span><span>{fmtTime(inc.end_time)}</span>
        </div>
      </div>
      <span className="hidden font-mono text-xs text-muted-foreground sm:block">risk {inc.risk_score.toFixed(2)}</span>
      <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </button>
  );
}

function FindingDrawer({ inc, onClose }) {
  const navigate = useNavigate();
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const triaged = !!inc.likely_intent;

  return (
    <div className="fixed inset-0 z-[100] flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className="relative z-10 flex h-full w-full max-w-lg flex-col border-l border-border bg-card shadow-lg animate-slide-in">
        {/* header */}
        <div className="flex items-start justify-between border-b border-border p-5">
          <div>
            <div className="mb-2 flex items-center gap-2">
              <SeverityBadge level={bandToLevel(inc.risk_band)} />
              <Badge variant="outline" className="font-mono">{inc.incident_id}</Badge>
              <Badge variant="primary">#{inc.risk_rank}</Badge>
            </div>
            <h2 className="text-lg font-semibold leading-snug">
              {inc.likely_intent || `${inc.event_count} correlated events`}
            </h2>
            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" /> {fmtTime(inc.start_time)} → {fmtTime(inc.end_time)} · {fmtDuration(inc.window_s)}
            </div>
          </div>
          <button onClick={onClose} className="rounded-btn p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
        </div>

        <div className="flex-1 space-y-5 overflow-y-auto scrollbar-thin p-5">
          {/* risk summary panel */}
          <div className="rounded-card border border-primary/20 bg-primary/5 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-primary">
              <Bot className="h-4 w-4" /> Risk Summary
            </div>
            {triaged ? (
              <>
                <p className="text-sm">{inc.likely_intent}</p>
                {inc.disambiguation && (
                  <p className="mt-2 text-sm text-muted-foreground"><span className="font-medium text-foreground">Why not benign: </span>{inc.disambiguation}</p>
                )}
                <div className="mt-3">
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Triage confidence</span>
                    <span className="font-mono font-medium">{fmtPct(inc.confidence)}</span>
                  </div>
                  <Progress value={(inc.confidence || 0) * 100} barClassName="bg-primary" />
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                This LOW-band incident was suppressed below the triage threshold; no LLM narrative was generated.
                Fused risk score {inc.risk_score.toFixed(3)}.
              </p>
            )}
          </div>

          {/* MITRE */}
          {triaged && inc.mitre?.length > 0 && (
            <Section title="MITRE ATT&CK">
              <div className="flex flex-wrap gap-1.5">
                {inc.mitre.map((m) => <Badge key={m} variant="danger" className="font-mono">{m}</Badge>)}
              </div>
            </Section>
          )}

          {/* key evidence */}
          {triaged && inc.key_evidence?.length > 0 && (
            <Section title="Key Evidence">
              <ul className="space-y-1.5 text-sm">
                {inc.key_evidence.map((e, n) => (
                  <li key={n} className="flex gap-2"><span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-primary" /> {e}</li>
                ))}
              </ul>
            </Section>
          )}

          {/* details grid */}
          <Section title="Details">
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Detail label="Risk score" value={inc.risk_score.toFixed(3)} mono />
              <Detail label="Severity floor" value={inc.severity_floor} />
              <Detail label="Events" value={inc.event_count} />
              <Detail label="Flagged / bridge" value={`${inc.n_flagged} / ${inc.n_bridge}`} />
              <Detail label="Tripwire hits" value={inc.tripwire_hits} />
              <Detail label="Max privilege" value={inc.max_privilege_level} />
              <Detail label="Sources (CT/K8s/IdP)" value={`${inc.source_cloudtrail_count}/${inc.source_k8s_count}/${inc.source_idp_count}`} mono />
              <Detail label="Edge types" value={(inc.edge_types || []).join(", ") || "—"} />
            </div>
          </Section>

          {/* participants */}
          <Section title="Participants">
            <Chips icon={Users} items={inc.principal_ids} />
            <Chips icon={Boxes} items={inc.namespaces} empty="no namespaces" />
            <Chips icon={Server} items={inc.resource_ids} empty="no resources" />
          </Section>

          {/* forensic snapshot — resource state captured at detection time, so the
              incident survives the resource's disappearance ("gone before triage") */}
          <div className="rounded-card border border-warning/30 bg-warning/5 p-4">
            <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-warning">
              <Camera className="h-4 w-4" /> Forensic Snapshot
            </div>
            <p className="mb-3 text-xs text-muted-foreground">
              Resource state captured at detection time — preserved even though the ephemeral
              asset has since been terminated.
            </p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Detail label="Captured at" value={fmtTime(inc.end_time)} mono />
              <Detail label="Resources observed" value={(inc.resource_ids || []).filter(Boolean).length || "—"} />
              <Detail label="Exposure window" value={inc.max_exposure_window_s ? fmtDuration(inc.max_exposure_window_s) : "—"} />
              <Detail label="Privileged in scope" value={inc.any_privileged ? "yes" : "no"} />
              <Detail label="Max privilege" value={inc.max_privilege_level} />
              <Detail label="Public exposure" value={inc.max_exposure_window_s > 0 ? "yes" : "no"} />
              <Detail label="Tripwires fired" value={inc.tripwire_hits} />
              <Detail label="Severity floor" value={inc.severity_floor} />
            </div>
          </div>

          {/* member events */}
          <Section title={`Top Member Events (by p_event)`}>
            <div className="overflow-hidden rounded-btn border border-border">
              <table className="w-full text-xs">
                <thead className="bg-surface text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1.5 text-left font-medium">Action</th>
                    <th className="px-2 py-1.5 text-left font-medium">Cohort</th>
                    <th className="px-2 py-1.5 text-right font-medium">p_event</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {inc.top_events.map((e) => (
                    <tr key={e.record_id}>
                      <td className="px-2 py-1.5"><span className="font-mono">{e.action}</span> <span className="text-muted-foreground">· {e.source}</span></td>
                      <td className="px-2 py-1.5 text-muted-foreground">{e.cohort}</td>
                      <td className="px-2 py-1.5 text-right font-mono">{(e.p_event ?? 0).toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          {/* recommended guardrails */}
          {triaged && inc.recommended_guardrails?.length > 0 && (
            <Section title="Recommended Guardrails">
              <ul className="space-y-1.5 text-sm">
                {inc.recommended_guardrails.map((g, n) => (
                  <li key={n} className="flex gap-2"><GitBranch className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" /> {g}</li>
                ))}
              </ul>
            </Section>
          )}
        </div>

        {/* footer actions */}
        <div className="flex items-center gap-2 border-t border-border p-4">
          <Button className="flex-1" onClick={() => navigate(`/app/chat?incident=${inc.incident_id}`)}>
            <Bot className="h-4 w-4" /> Ask AI Analyst
          </Button>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div>
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</div>
      {children}
    </div>
  );
}
function Detail({ label, value, mono }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-0.5", mono && "font-mono")}>{value}</div>
    </div>
  );
}
function Chips({ icon: Icon, items, empty }) {
  const list = (items || []).filter(Boolean);
  return (
    <div className="mb-2 flex items-start gap-2">
      <Icon className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <div className="flex flex-wrap gap-1.5">
        {list.length === 0
          ? <span className="text-xs text-muted-foreground">{empty}</span>
          : list.map((x) => <Badge key={x} variant="outline" className="font-mono">{x}</Badge>)}
      </div>
    </div>
  );
}
