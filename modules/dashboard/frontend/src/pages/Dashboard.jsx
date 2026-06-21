import { useNavigate } from "react-router-dom";
import {
  ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import {
  ShieldAlert, Boxes, Network, AlertTriangle, RefreshCw, ArrowUpRight, ArrowDownRight, Filter,
} from "lucide-react";
import { useData } from "../lib/data";
import { PageHeader, Sparkline, PageState, StatPill } from "../components/shared";
import { Button, Card, SeverityBadge, Badge } from "../components/ui";
import ReplayPanel from "../components/ReplayPanel";
import { CHART, SEVERITY_COLOR, axisProps, ChartTooltip } from "../components/charts";
import { bandToLevel, fmtNum, fmtTime, cn } from "../lib/utils";

const KPI_ICON = { findings: ShieldAlert, resources: Boxes, clusters: Network, critical: AlertTriangle };

export default function Dashboard() {
  const { data, loading, error } = useData();
  const navigate = useNavigate();

  return (
    <PageState loading={loading} error={error}>
      {data && <DashboardBody data={data} navigate={navigate} />}
    </PageState>
  );
}

function DashboardBody({ data, navigate }) {
  const { metrics, incidents, replay } = data;
  const funnel = metrics.alert_fatigue;
  const maxFunnel = Math.max(...funnel.map((f) => f.value));
  const reduction = Math.round((1 - funnel[funnel.length - 2].value / funnel[0].value) * 100); // raw -> incidents
  const latest = [...incidents]
    .filter((i) => i.risk_band !== "LOW")
    .sort((a, b) => (b.end_time || "").localeCompare(a.end_time || ""))
    .slice(0, 6);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resource Risk Dashboard"
        description="Live overview of ephemeral cloud and Kubernetes resource risk."
        breadcrumb={["Console", "Dashboard"]}
      >
        <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
        <Button size="sm" onClick={() => navigate("/app/reports")}>Export</Button>
      </PageHeader>

      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metrics.kpis.map((k) => {
          const Icon = KPI_ICON[k.id] || ShieldAlert;
          const up = k.trend === "up";
          return (
            <Card key={k.id} className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex h-9 w-9 items-center justify-center rounded-btn bg-primary/10 text-primary">
                  <Icon className="h-[18px] w-[18px]" />
                </div>
                <Sparkline data={k.spark} up={up} />
              </div>
              <div className="mt-3 text-2xl font-bold">{fmtNum(k.value)}</div>
              <div className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
                <span>{k.label}</span>
              </div>
              <div className="mt-1 flex items-center gap-1">
                {k.trend !== "flat" && (up
                  ? <ArrowUpRight className="h-3.5 w-3.5 text-success" />
                  : <ArrowDownRight className="h-3.5 w-3.5 text-danger" />)}
                <StatPill trend={k.trend}>{k.delta > 0 ? `+${k.delta}` : k.delta}</StatPill>
                <span className="text-xs text-muted-foreground">vs. prior window</span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Replay simulation — hero */}
      <ReplayPanel replay={replay} />

      {/* Alert-fatigue funnel + severity donut */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-semibold leading-tight tracking-tight">Alert-Fatigue Reduction</h3>
              <p className="text-xs text-muted-foreground">From raw events to correlated, triaged incidents.</p>
            </div>
            <Badge variant="success">{reduction}% fewer alerts to triage</Badge>
          </div>
          <div className="space-y-2.5">
            {funnel.map((f, i) => (
              <div key={f.stage} className="flex items-center gap-3">
                <div className="w-40 shrink-0 text-sm text-muted-foreground">{f.stage}</div>
                <div className="h-7 flex-1 overflow-hidden rounded-btn bg-muted">
                  <div
                    className={cn("flex h-full items-center justify-end rounded-btn px-2 text-xs font-semibold text-white",
                      i === 0 ? "bg-info" : i === funnel.length - 1 ? "bg-primary" : "bg-warning")}
                    style={{ width: `${Math.max((f.value / maxFunnel) * 100, 6)}%` }}
                  >
                    {fmtNum(f.value)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <h3 className="mb-2 font-semibold leading-tight tracking-tight">Findings by Risk</h3>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={metrics.severity_breakdown} dataKey="value" nameKey="name" innerRadius={48} outerRadius={72} paddingAngle={2}>
                  {metrics.severity_breakdown.map((s) => <Cell key={s.name} fill={SEVERITY_COLOR[s.name]} />)}
                </Pie>
                <Tooltip content={<ChartTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 space-y-1.5">
            {metrics.severity_breakdown.map((s) => (
              <div key={s.name} className="flex items-center gap-2 text-sm">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: SEVERITY_COLOR[s.name] }} />
                <span className="text-muted-foreground">{s.name}</span>
                <span className="ml-auto font-mono font-medium">{s.value}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Risk trend + latest findings */}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2 p-5">
          <h3 className="mb-4 font-semibold leading-tight tracking-tight">Incidents by Severity (per day)</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metrics.risk_trend} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="day" {...axisProps} tickFormatter={(d) => d.slice(5)} />
                <YAxis {...axisProps} allowDecimals={false} width={32} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="critical" name="Critical" stroke={CHART.danger} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="high" name="High" stroke={CHART.warning} strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="low" name="Low" stroke={CHART.success} strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold leading-tight tracking-tight">Latest Risk Findings</h3>
            <Button variant="link" size="sm" className="h-auto p-0" onClick={() => navigate("/app/findings")}>View all</Button>
          </div>
          <div className="space-y-1">
            {latest.map((i) => (
              <button
                key={i.incident_id}
                onClick={() => navigate(`/app/findings?incident=${i.incident_id}`)}
                className="flex w-full items-start gap-3 rounded-btn px-2 py-2 text-left hover:bg-muted"
              >
                <SeverityBadge level={bandToLevel(i.risk_band)} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{i.likely_intent || `${i.event_count} correlated events`}</div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-mono">{i.incident_id}</span>
                    <span>·</span>
                    <span>{fmtTime(i.end_time)}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </Card>
      </div>

      {/* Riskiest namespaces + cohorts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <TopList title="Riskiest Namespaces" icon={Boxes} rows={metrics.top_namespaces} />
        <TopList title="Riskiest Cohorts" icon={Filter} rows={metrics.top_cohorts} />
      </div>
    </div>
  );
}

function TopList({ title, icon: Icon, rows }) {
  const max = Math.max(...rows.map((r) => r.score), 1);
  return (
    <Card className="p-5">
      <h3 className="mb-3 flex items-center gap-2 font-semibold leading-tight tracking-tight">
        <Icon className="h-4 w-4 text-muted-foreground" /> {title}
      </h3>
      <div className="space-y-2.5">
        {rows.map((r) => (
          <div key={r.name} className="flex items-center gap-3">
            <span className="w-40 shrink-0 truncate font-mono text-sm">{r.name}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${(r.score / max) * 100}%` }} />
            </div>
            <span className="w-16 shrink-0 text-right text-xs text-muted-foreground">{r.incidents} inc.</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
