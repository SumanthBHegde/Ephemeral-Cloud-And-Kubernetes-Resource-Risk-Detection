/* Shared recharts styling: muted axes, dashed grid, custom tooltip, semantic colors. */
export const CHART = {
  primary: "hsl(var(--primary))",
  danger: "hsl(var(--danger))",
  warning: "hsl(var(--warning))",
  info: "hsl(var(--info))",
  success: "hsl(var(--success))",
  grid: "hsl(var(--border))",
  axis: "hsl(var(--muted-foreground))",
};

export const SEVERITY_COLOR = {
  Critical: CHART.danger,
  High: CHART.warning,
  Medium: CHART.info,
  Low: CHART.success,
};

export const SOURCE_COLOR = {
  cloudtrail: CHART.primary,
  k8s: CHART.info,
  idp: CHART.warning,
};

export const axisProps = {
  tick: { fontSize: 12, fill: CHART.axis },
  tickLine: false,
  axisLine: { stroke: CHART.grid },
};

export function ChartTooltip({ active, payload, label, labelFormatter, valueFormatter }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-btn border border-border bg-popover px-3 py-2 text-xs shadow-md">
      {label != null && (
        <div className="mb-1 font-medium text-foreground">
          {labelFormatter ? labelFormatter(label) : label}
        </div>
      )}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.fill }} />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="ml-auto font-mono font-medium text-foreground">
            {valueFormatter ? valueFormatter(p.value) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}
