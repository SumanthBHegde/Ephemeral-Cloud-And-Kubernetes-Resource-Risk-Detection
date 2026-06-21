import { useState } from "react";
import { User, Palette, SlidersHorizontal, Sun, Moon, Check } from "lucide-react";
import { useTheme } from "../lib/theme";
import { PageHeader } from "../components/shared";
import { Card, Button, Input, Label, Switch, Separator, Avatar, Badge } from "../components/ui";
import { cn } from "../lib/utils";

const TABS = [
  { id: "account", label: "Account", icon: User },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "preferences", label: "Preferences", icon: SlidersHorizontal },
];

export default function Settings() {
  const [tab, setTab] = useState("account");
  return (
    <div>
      <PageHeader title="Settings" description="Manage your account and console preferences." breadcrumb={["Console", "Settings"]} />
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <Card className="h-fit p-2">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn("flex w-full items-center gap-2.5 rounded-btn px-3 py-2 text-sm font-medium transition-colors",
                tab === t.id ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground")}
            >
              <t.icon className="h-4 w-4" /> {t.label}
            </button>
          ))}
        </Card>

        <div>
          {tab === "account" && <AccountTab />}
          {tab === "appearance" && <AppearanceTab />}
          {tab === "preferences" && <PreferencesTab />}
        </div>
      </div>
    </div>
  );
}

function AccountTab() {
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-semibold">Account</h3>
      <div className="mb-5 flex items-center gap-4">
        <Avatar name="Sumanth Hegde" className="h-14 w-14 text-lg" />
        <div>
          <div className="font-medium">Sumanth Hegde</div>
          <Badge variant="primary" className="mt-1">Cloud Security Analyst</Badge>
        </div>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div><Label>Full name</Label><Input className="mt-1.5" defaultValue="Sumanth Hegde" /></div>
        <div><Label>Email</Label><Input className="mt-1.5" defaultValue="analyst@sentinel.io" /></div>
        <div><Label>Role</Label><Input className="mt-1.5" defaultValue="Cloud Security Analyst" /></div>
        <div><Label>Team</Label><Input className="mt-1.5" defaultValue="Detection & Response" /></div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="outline">Cancel</Button>
        <Button>Save changes</Button>
      </div>
    </Card>
  );
}

function AppearanceTab() {
  const { theme, setTheme } = useTheme();
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-semibold">Appearance</h3>
      <Label>Theme</Label>
      <div className="mt-2 grid max-w-md grid-cols-2 gap-3">
        {[
          { id: "light", label: "Light", icon: Sun },
          { id: "dark", label: "Dark", icon: Moon },
        ].map((opt) => (
          <button
            key={opt.id}
            onClick={() => setTheme(opt.id)}
            className={cn("relative flex items-center gap-2 rounded-card border p-4 text-sm font-medium transition-all",
              theme === opt.id ? "border-primary bg-primary/5 text-primary" : "border-border hover:border-ring")}
          >
            <opt.icon className="h-4 w-4" /> {opt.label}
            {theme === opt.id && <Check className="absolute right-3 top-3 h-4 w-4 text-primary" />}
          </button>
        ))}
      </div>
    </Card>
  );
}

function PreferencesTab() {
  const [prefs, setPrefs] = useState({ liveReplay: true, compact: false, monoIds: true, autoTriage: true });
  const set = (k) => (v) => setPrefs((p) => ({ ...p, [k]: v }));
  return (
    <Card className="p-5">
      <h3 className="mb-4 font-semibold">Preferences</h3>
      <div className="space-y-3 text-sm">
        <Row label="Auto-play replay on dashboard" desc="Start the live replay simulation when the dashboard loads." checked={prefs.liveReplay} onChange={set("liveReplay")} />
        <Separator />
        <Row label="Compact density" desc="Reduce padding across tables and cards." checked={prefs.compact} onChange={set("compact")} />
        <Separator />
        <Row label="Monospace identifiers" desc="Render resource IDs and namespaces in JetBrains Mono." checked={prefs.monoIds} onChange={set("monoIds")} />
        <Separator />
        <Row label="Show triage narratives" desc="Display LLM triage summaries in the finding drawer." checked={prefs.autoTriage} onChange={set("autoTriage")} />
      </div>
    </Card>
  );
}

function Row({ label, desc, checked, onChange }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <div className="font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{desc}</div>
      </div>
      <Switch checked={checked} onChange={onChange} />
    </div>
  );
}
