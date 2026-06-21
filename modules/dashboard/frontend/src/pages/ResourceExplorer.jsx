import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Boxes, Activity, AlertTriangle, Sigma } from "lucide-react";
import { useData } from "../lib/data";
import { PageHeader, PageState, EmptyState } from "../components/shared";
import { Card, Badge, SeverityBadge, SearchInput, Select, Progress } from "../components/ui";
import { bandToLevel, fmtTime, fmtNum, cn } from "../lib/utils";

const PAGE_SIZE = 25;
const COLUMNS = [
  { key: "record_id", label: "Record", sortable: true },
  { key: "source", label: "Source", sortable: true },
  { key: "action", label: "Action", sortable: true },
  { key: "cohort", label: "Cohort", sortable: true },
  { key: "resource_id", label: "Resource / Namespace", sortable: false },
  { key: "event_time", label: "Time (UTC)", sortable: true },
  { key: "p_event", label: "Risk (p_event)", sortable: true },
  { key: "risk_band", label: "Incident", sortable: true },
];

export default function ResourceExplorer() {
  const { data, loading, error } = useData();
  return (
    <PageState loading={loading} error={error}>
      {data && <ExplorerBody events={data.events} />}
    </PageState>
  );
}

function ExplorerBody({ events }) {
  const [q, setQ] = useState("");
  const [source, setSource] = useState("ALL");
  const [cohort, setCohort] = useState("ALL");
  const [sort, setSort] = useState({ key: "p_event", dir: "desc" });
  const [page, setPage] = useState(0);

  const sources = useMemo(() => ["ALL", ...[...new Set(events.map((e) => e.source))].sort()], [events]);
  const cohorts = useMemo(() => ["ALL", ...[...new Set(events.map((e) => e.cohort))].sort()], [events]);

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    let rows = events.filter((e) => {
      if (source !== "ALL" && e.source !== source) return false;
      if (cohort !== "ALL" && e.cohort !== cohort) return false;
      if (ql) {
        const hay = `${e.record_id} ${e.action} ${e.principal_id} ${e.resource_id || ""} ${e.namespace || ""}`.toLowerCase();
        if (!hay.includes(ql)) return false;
      }
      return true;
    });
    const { key, dir } = sort;
    rows = [...rows].sort((a, b) => {
      const av = a[key] ?? "", bv = b[key] ?? "";
      const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
      return dir === "asc" ? cmp : -cmp;
    });
    return rows;
  }, [events, q, source, cohort, sort]);

  const inIncident = useMemo(() => events.filter((e) => e.incident_id).length, [events]);
  const flagged = useMemo(() => events.filter((e) => (e.p_event ?? 0) >= 0.5).length, [events]);

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE) || 1;
  const safePage = Math.min(page, pageCount - 1);
  const rows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const toggleSort = (key) =>
    setSort((s) => (s.key === key ? { key, dir: s.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));

  const reset = () => setPage(0);

  return (
    <div>
      <PageHeader
        title="Resource Explorer"
        description="Enriched ephemeral resource/event stream with behavioral cohorts and per-event risk."
        breadcrumb={["Console", "Resource Explorer"]}
      />

      <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Mini icon={Sigma} label="Total events" value={fmtNum(events.length)} />
        <Mini icon={Boxes} label="In an incident" value={fmtNum(inIncident)} />
        <Mini icon={AlertTriangle} label="High-risk events (p≥0.5)" value={fmtNum(flagged)} />
        <Mini icon={Activity} label="Cohorts" value={cohorts.length - 1} />
      </div>

      <Card>
        <div className="flex flex-col gap-3 border-b border-border p-3 sm:flex-row sm:items-center">
          <SearchInput className="sm:max-w-xs" placeholder="Search record, action, principal, resource…"
            value={q} onChange={(e) => { setQ(e.target.value); reset(); }} />
          <Select value={source} onChange={(e) => { setSource(e.target.value); reset(); }} className="sm:w-40">
            {sources.map((s) => <option key={s} value={s}>{s === "ALL" ? "All sources" : s}</option>)}
          </Select>
          <Select value={cohort} onChange={(e) => { setCohort(e.target.value); reset(); }} className="sm:w-44">
            {cohorts.map((c) => <option key={c} value={c}>{c === "ALL" ? "All cohorts" : c}</option>)}
          </Select>
          <span className="text-sm text-muted-foreground sm:ml-auto">{fmtNum(filtered.length)} rows</span>
        </div>

        {filtered.length === 0 ? (
          <EmptyState icon={Boxes} title="No events match" description="Adjust your filters." />
        ) : (
          <div className="overflow-x-auto scrollbar-thin">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="border-b border-border bg-surface text-xs text-muted-foreground">
                <tr>
                  {COLUMNS.map((c) => (
                    <th key={c.key} className="px-3 py-2 text-left font-medium">
                      {c.sortable ? (
                        <button onClick={() => toggleSort(c.key)} className="inline-flex items-center gap-1 hover:text-foreground">
                          {c.label}
                          {sort.key === c.key && (sort.dir === "asc" ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                        </button>
                      ) : c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map((e) => (
                  <tr key={e.record_id} className="hover:bg-muted/50">
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{e.record_id.slice(0, 8)}</td>
                    <td className="px-3 py-2"><Badge variant="outline">{e.source}</Badge></td>
                    <td className="px-3 py-2 font-mono text-xs">{e.action}</td>
                    <td className="px-3 py-2 text-muted-foreground">{e.cohort}</td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{e.resource_id || e.namespace || "—"}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">{fmtTime(e.event_time)}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Progress value={(e.p_event ?? 0) * 100} className="h-1.5 w-16"
                          barClassName={(e.p_event ?? 0) >= 0.6 ? "bg-danger" : (e.p_event ?? 0) >= 0.3 ? "bg-warning" : "bg-success"} />
                        <span className="font-mono text-xs">{(e.p_event ?? 0).toFixed(2)}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      {e.risk_band ? <SeverityBadge level={bandToLevel(e.risk_band)} /> : <span className="text-xs text-muted-foreground">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* pagination */}
        {filtered.length > 0 && (
          <div className="flex items-center justify-between border-t border-border p-3 text-sm">
            <span className="text-muted-foreground">
              Page {safePage + 1} of {pageCount}
            </span>
            <div className="flex items-center gap-1">
              <button disabled={safePage === 0} onClick={() => setPage(safePage - 1)}
                className="flex h-8 w-8 items-center justify-center rounded-btn border border-border disabled:opacity-40 hover:bg-muted">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}
                className="flex h-8 w-8 items-center justify-center rounded-btn border border-border disabled:opacity-40 hover:bg-muted">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function Mini({ icon: Icon, label, value }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Icon className="h-4 w-4" /> {label}
      </div>
      <div className="mt-1.5 text-2xl font-bold">{value}</div>
    </Card>
  );
}
