import { useState } from "react";
import { Printer, Share2, Download, FileText, Sparkles, ShieldCheck } from "lucide-react";
import { useData } from "../lib/data";
import { PageHeader, PageState } from "../components/shared";
import { Card, Badge, SeverityBadge, Progress, Button } from "../components/ui";
import { bandToLevel, fmtTime, cn } from "../lib/utils";

export default function Reports() {
  const { data, loading, error } = useData();
  return (
    <PageState loading={loading} error={error}>
      {data && <ReportsBody reports={data.reports} />}
    </PageState>
  );
}

function ReportsBody({ reports }) {
  const [active, setActive] = useState(reports[0]?.id);
  const doc = reports.find((r) => r.id === active) || reports[0];

  return (
    <div>
      <PageHeader
        title="Risk Reports"
        description="Auto-generated incident reports from the triage agent."
        breadcrumb={["Console", "Reports"]}
      />

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        {/* report list */}
        <Card className="h-fit divide-y divide-border">
          {reports.map((r) => (
            <button
              key={r.id}
              onClick={() => setActive(r.id)}
              className={cn("flex w-full items-start gap-3 p-3 text-left transition-colors",
                r.id === active ? "bg-primary/5" : "hover:bg-muted")}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-btn bg-primary/10 text-primary">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium">{r.id}</div>
                <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{r.title.split(" — ")[1]}</div>
              </div>
              <SeverityBadge level={bandToLevel(r.risk_band)} />
            </button>
          ))}
        </Card>

        {/* document preview */}
        {doc && (
          <Card className="p-0">
            <div className="flex items-center justify-between border-b border-border p-4">
              <div className="flex items-center gap-2">
                <Badge variant="primary"><Sparkles className="h-3 w-3" /> AI-Generated</Badge>
                <Badge variant="success"><ShieldCheck className="h-3 w-3" /> Reviewed</Badge>
              </div>
              <div className="flex items-center gap-1">
                {[Printer, Share2, Download].map((Icon, i) => (
                  <button key={i} className="flex h-8 w-8 items-center justify-center rounded-btn border border-border text-muted-foreground hover:bg-muted">
                    <Icon className="h-4 w-4" />
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-6 p-6">
              <div>
                <div className="mb-1 flex items-center gap-2">
                  <SeverityBadge level={bandToLevel(doc.risk_band)} />
                  <Badge variant="outline" className="font-mono">{doc.id}</Badge>
                </div>
                <h2 className="text-xl font-bold tracking-tight">{doc.title}</h2>
                <p className="mt-1 text-xs text-muted-foreground">Generated {fmtTime(doc.generated_at)} · confidence {Math.round((doc.confidence || 0) * 100)}%</p>
              </div>

              {doc.sections.map((s) => (
                <div key={s.heading}>
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="font-semibold">{s.heading}</h3>
                    <div className="flex w-32 items-center gap-2">
                      <Progress value={(s.confidence || 0) * 100} className="h-1.5" />
                      <span className="text-xs text-muted-foreground">{Math.round((s.confidence || 0) * 100)}%</span>
                    </div>
                  </div>
                  <div className="whitespace-pre-line text-sm text-muted-foreground">{s.body || "—"}</div>
                </div>
              ))}

              <div>
                <h3 className="mb-2 font-semibold">Referenced Findings</h3>
                <div className="flex flex-wrap gap-1.5">
                  {doc.referenced_findings.map((f) => (
                    <Badge key={f} variant="outline" className="font-mono">{typeof f === "string" ? f.slice(0, 12) : f}</Badge>
                  ))}
                </div>
              </div>

              <p className="border-t border-border pt-4 text-xs text-muted-foreground">{doc.disclaimer}</p>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
