import { useMemo, useState } from "react";
import { Bell, ShieldAlert, Settings2 } from "lucide-react";
import { useData } from "../lib/data";
import { PageHeader, PageState, EmptyState } from "../components/shared";
import { Card, Badge, SeverityBadge, Switch, Tabs, TabsList, TabsTrigger, Separator } from "../components/ui";
import { fmtTime, cn } from "../lib/utils";

const FILTERS = ["All", "Unread", "Critical"];

export default function Notifications() {
  const { data, loading, error } = useData();
  return (
    <PageState loading={loading} error={error}>
      {data && <NotificationsBody items={data.notifications} />}
    </PageState>
  );
}

function NotificationsBody({ items }) {
  const [filter, setFilter] = useState("All");
  const [prefs, setPrefs] = useState({ critical: true, high: true, digest: false, email: true });

  const filtered = useMemo(() => items.filter((n) => {
    if (filter === "Unread") return !n.read;
    if (filter === "Critical") return n.severity === "Critical";
    return true;
  }), [items, filter]);

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="Alerts raised from CRITICAL and HIGH risk findings."
        breadcrumb={["Console", "Notifications"]}
      />

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        <div>
          <div className="mb-3">
            <Tabs value={filter} onValueChange={setFilter}>
              <TabsList>
                {FILTERS.map((f) => <TabsTrigger key={f} value={f}>{f}</TabsTrigger>)}
              </TabsList>
            </Tabs>
          </div>

          {filtered.length === 0 ? (
            <EmptyState icon={Bell} title="Nothing here" description="No notifications match this filter." />
          ) : (
            <Card className="divide-y divide-border">
              {filtered.map((n) => (
                <div key={n.id} className="flex items-start gap-3 p-4">
                  <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-btn",
                    n.severity === "Critical" ? "bg-danger/10 text-danger" : n.severity === "High" ? "bg-warning/10 text-warning" : "bg-info/10 text-info")}>
                    <ShieldAlert className="h-[18px] w-[18px]" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{n.title}</span>
                      <SeverityBadge level={n.severity} />
                      {!n.read && <span className="h-2 w-2 rounded-full bg-primary" />}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">{n.body}</p>
                    <span className="mt-1 block text-xs text-muted-foreground">{fmtTime(n.time)}</span>
                  </div>
                </div>
              ))}
            </Card>
          )}
        </div>

        {/* preferences */}
        <Card className="h-fit p-5">
          <h3 className="mb-3 flex items-center gap-2 font-semibold"><Settings2 className="h-4 w-4 text-muted-foreground" /> Preferences</h3>
          <div className="space-y-3 text-sm">
            <Pref label="Critical findings" checked={prefs.critical} onChange={(v) => setPrefs((p) => ({ ...p, critical: v }))} />
            <Pref label="High findings" checked={prefs.high} onChange={(v) => setPrefs((p) => ({ ...p, high: v }))} />
            <Separator />
            <Pref label="Daily digest" checked={prefs.digest} onChange={(v) => setPrefs((p) => ({ ...p, digest: v }))} />
            <Pref label="Email alerts" checked={prefs.email} onChange={(v) => setPrefs((p) => ({ ...p, email: v }))} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function Pref({ label, checked, onChange }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-muted-foreground">{label}</span>
      <Switch checked={checked} onChange={onChange} />
    </div>
  );
}
