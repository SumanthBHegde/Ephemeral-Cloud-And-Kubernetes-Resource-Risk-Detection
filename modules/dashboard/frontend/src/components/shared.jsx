import { cn } from "../lib/utils";

export function PageHeader({ title, description, children, breadcrumb }) {
  return (
    <div className="mb-6">
      {breadcrumb && (
        <div className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          {breadcrumb.map((b, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && <span>/</span>}
              <span className={i === breadcrumb.length - 1 ? "text-foreground" : ""}>{b}</span>
            </span>
          ))}
        </div>
      )}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
      </div>
    </div>
  );
}

export function Sparkline({ data, className, color = "hsl(var(--primary))", up = true }) {
  const w = 80, h = 28;
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const pts = data.map((d, i) => `${(i / (data.length - 1)) * w},${h - ((d - min) / range) * h}`);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={cn("h-7 w-20", className)} preserveAspectRatio="none">
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function EmptyState({ icon: Icon, title, description, children }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-card border border-dashed border-border py-16 text-center">
      {Icon && <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground"><Icon className="h-6 w-6" /></div>}
      <h3 className="font-semibold">{title}</h3>
      {description && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}

export function StatPill({ trend, children }) {
  const cls = trend === "up" ? "text-success" : trend === "down" ? "text-danger" : "text-muted-foreground";
  return <span className={cn("text-xs font-semibold", cls)}>{children}</span>;
}

/* Loading / error gate used by data-backed pages. */
export function PageState({ loading, error, children }) {
  if (error) {
    return (
      <div className="rounded-card border border-dashed border-danger/40 bg-danger/5 p-8 text-center">
        <h3 className="font-semibold text-danger">Could not load pipeline data</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {String(error.message || error)}. Run <code className="font-mono">python -m modules.dashboard.build</code> to regenerate the JSON.
        </p>
      </div>
    );
  }
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="shimmer h-24 w-full rounded-card bg-muted" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="shimmer h-28 rounded-card bg-muted" />)}
        </div>
        <div className="shimmer h-80 w-full rounded-card bg-muted" />
      </div>
    );
  }
  return children;
}
