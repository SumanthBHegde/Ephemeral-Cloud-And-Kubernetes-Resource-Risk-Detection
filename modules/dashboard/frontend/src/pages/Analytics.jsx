import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from "recharts";
import { useData } from "../lib/data";
import { PageHeader, PageState } from "../components/shared";
import { Card } from "../components/ui";
import { CHART, SEVERITY_COLOR, axisProps, ChartTooltip } from "../components/charts";

export default function Analytics() {
  const { data, loading, error } = useData();
  return (
    <PageState loading={loading} error={error}>
      {data && <AnalyticsBody metrics={data.metrics} />}
    </PageState>
  );
}

function Panel({ title, description, children, className }) {
  return (
    <Card className={"p-5 " + (className || "")}>
      <div className="mb-4">
        <h3 className="font-semibold leading-tight tracking-tight">{title}</h3>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      <div className="h-64">{children}</div>
    </Card>
  );
}

function AnalyticsBody({ metrics }) {
  const cohortRadar = metrics.cohort_distribution.map((c) => ({ name: c.name, value: c.value }));
  const funnel = metrics.alert_fatigue;
  // reliability curve: predicted probability vs observed malicious rate per bin.
  // `ideal` is the y=x diagonal — points on it mean a 0.8 score really is ~80% malicious.
  const calibration = (metrics.calibration || []).map((c) => ({
    predicted: c.predicted, observed: c.observed, ideal: c.predicted, n: c.n,
  }));

  return (
    <div>
      <PageHeader
        title="Risk Analytics"
        description="Distributions, trends, and calibration across the detection pipeline — including the alert-fatigue funnel and risk-score reliability."
        breadcrumb={["Console", "Analytics"]}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Risk Trend" description="Incidents per day by severity band.">
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
        </Panel>

        <Panel title="MITRE ATT&CK Frequency" description="Techniques across triaged incidents.">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={metrics.mitre_frequency} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
              <XAxis type="number" {...axisProps} allowDecimals={false} />
              <YAxis type="category" dataKey="code" {...axisProps} width={70} />
              <Tooltip content={<ChartTooltip labelFormatter={(c) => {
                const m = metrics.mitre_frequency.find((x) => x.code === c);
                return m ? `${m.code} — ${m.name}` : c;
              }} />} />
              <Bar dataKey="count" name="Incidents" fill={CHART.primary} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Events by Source" description="Normalized event volume per telemetry source.">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={metrics.source_breakdown} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="name" {...axisProps} />
              <YAxis {...axisProps} width={44} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="value" name="Events" fill={CHART.info} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Cohort Intensity" description="Event distribution across behavioral cohorts.">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={cohortRadar} outerRadius="72%">
              <PolarGrid stroke={CHART.grid} />
              <PolarAngleAxis dataKey="name" tick={{ fontSize: 11, fill: CHART.axis }} />
              <PolarRadiusAxis tick={{ fontSize: 10, fill: CHART.axis }} />
              <Tooltip content={<ChartTooltip />} />
              <Radar name="Events" dataKey="value" stroke={CHART.primary} fill={CHART.primary} fillOpacity={0.3} />
            </RadarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Findings by Risk Band" description="Severity distribution of correlated incidents.">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={metrics.severity_breakdown} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                {metrics.severity_breakdown.map((s) => <Cell key={s.name} fill={SEVERITY_COLOR[s.name]} />)}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Alert-Fatigue Funnel" description="Raw events → flagged → suppressed → correlated → triaged.">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={funnel} layout="vertical" margin={{ top: 4, right: 24, left: 40, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
              <XAxis type="number" {...axisProps} />
              <YAxis type="category" dataKey="stage" {...axisProps} width={120} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="value" name="Count" fill={CHART.primary} radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        {calibration.length > 0 && (
          <Panel title="Risk Calibration" description="Predicted risk vs observed malicious rate — a 0.8 score means ~80% malicious.">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={calibration} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                <XAxis type="number" dataKey="predicted" domain={[0, 1]} {...axisProps}
                  tickFormatter={(v) => v.toFixed(1)} />
                <YAxis type="number" domain={[0, 1]} {...axisProps} width={36}
                  tickFormatter={(v) => v.toFixed(1)} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="ideal" name="Perfect calibration" stroke={CHART.grid}
                  strokeWidth={1.5} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
                <Line type="monotone" dataKey="observed" name="Observed" stroke={CHART.primary}
                  strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </Panel>
        )}
      </div>
    </div>
  );
}
