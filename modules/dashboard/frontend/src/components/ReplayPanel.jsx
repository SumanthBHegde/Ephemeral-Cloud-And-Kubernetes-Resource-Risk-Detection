import { useEffect, useMemo, useRef, useState } from "react";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";
import { Play, Pause, RotateCcw, Radio, Clock, ShieldAlert, ScanLine } from "lucide-react";
import ReplayEngine from "../lib/ReplayEngine";
import { Badge } from "./ui";
import { CHART, SOURCE_COLOR, axisProps, ChartTooltip } from "./charts";
import { cn, fmtTime } from "../lib/utils";

const SPEEDS = [0.5, 1, 2];

function hhmm(iso) {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" });
}

export default function ReplayPanel({ replay }) {
  const engineRef = useRef(null);
  const [snap, setSnap] = useState(null);

  if (!engineRef.current) engineRef.current = new ReplayEngine(replay);

  useEffect(() => {
    const engine = engineRef.current;
    const unsub = engine.subscribe(setSnap);
    // Autoplay from the start of the demo window on mount so the before/after
    // detection payoff is reached without a click (recorded-demo + live-link friendly).
    engine.reset();
    engine.play();
    return () => { unsub(); engine.destroy(); };
  }, []);

  const engine = engineRef.current;
  const range = snap?.range || "demo";

  // active-range bins; reveal each source value only once the clock passes the bin
  const chartData = useMemo(() => {
    if (!snap) return [];
    const start = range === "demo" ? Date.parse(replay.meta.demo_window.t_start) : Date.parse(replay.meta.t_start);
    const end = range === "demo" ? Date.parse(replay.meta.demo_window.t_end) : Date.parse(replay.meta.t_end);
    return replay.timeline_bins
      .filter((b) => { const ms = Date.parse(b.t); return ms >= start && ms <= end; })
      .map((b) => {
        const ms = Date.parse(b.t);
        const shown = ms <= snap.clockMs;
        return {
          t: b.t, label: hhmm(b.t),
          cloudtrail: shown ? b.cloudtrail : null,
          k8s: shown ? b.k8s : null,
          idp: shown ? b.idp : null,
        };
      });
  }, [snap, range, replay]);

  // the demo incident's formation + traditional-scan contrast
  const demoIncId = replay.meta.demo_window.incident_id;
  const demoInc = replay.incidents.find((i) => i.incident_id === demoIncId);
  const formationLabel = demoInc ? hhmm(demoInc.formation_time) : null;
  const formationCrossed = snap && demoInc && snap.clockMs >= Date.parse(demoInc.formation_time);

  const formed = snap?.formedIncidents || [];
  const critFormed = formed.filter((i) => i.risk_band === "CRITICAL").length;

  return (
    <div className="rounded-card border border-border bg-card shadow-sm">
      <div className="flex flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-btn bg-primary/10 text-primary">
            <Radio className="h-[18px] w-[18px]" />
          </div>
          <div>
            <h3 className="font-semibold leading-tight tracking-tight">Live Replay Simulation</h3>
            <p className="text-xs text-muted-foreground">
              {range === "demo" ? replay.meta.demo_window.label : "Full 5-day telemetry timeline"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-btn border border-border bg-surface p-1 text-xs">
          {["demo", "full"].map((r) => (
            <button
              key={r}
              onClick={() => engine.setRange(r)}
              className={cn("rounded-[6px] px-2.5 py-1 font-medium transition-all",
                range === r ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}
            >
              {r === "demo" ? "Demo Window" : "Full Timeline"}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        {/* live counters */}
        <div className="mb-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Counter icon={Clock} label="Virtual clock" value={snap ? fmtTime(snap.clockTime) : "—"} mono />
          <Counter icon={ScanLine} label="Events seen" value={snap ? snap.eventsSeen.toLocaleString() : "0"} />
          <Counter icon={ShieldAlert} label="Incidents formed" value={formed.length} />
          <Counter icon={ShieldAlert} label="Critical formed" value={critFormed} danger />
        </div>

        {/* timeline chart */}
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                {Object.entries(SOURCE_COLOR).map(([k, c]) => (
                  <linearGradient key={k} id={`g-${k}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={c} stopOpacity={0.5} />
                    <stop offset="95%" stopColor={c} stopOpacity={0.05} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="label" {...axisProps} minTickGap={24} />
              <YAxis {...axisProps} allowDecimals={false} width={36} />
              <Tooltip content={<ChartTooltip />} />
              {formationCrossed && formationLabel && (
                <ReferenceLine x={formationLabel} stroke={CHART.danger} strokeDasharray="4 2"
                  label={{ value: "incident formed", fontSize: 10, fill: CHART.danger, position: "insideTopRight" }} />
              )}
              <Area type="monotone" dataKey="cloudtrail" name="CloudTrail" stackId="1" stroke={SOURCE_COLOR.cloudtrail} fill="url(#g-cloudtrail)" isAnimationActive={false} connectNulls={false} />
              <Area type="monotone" dataKey="k8s" name="K8s audit" stackId="1" stroke={SOURCE_COLOR.k8s} fill="url(#g-k8s)" isAnimationActive={false} connectNulls={false} />
              <Area type="monotone" dataKey="idp" name="IdP session" stackId="1" stroke={SOURCE_COLOR.idp} fill="url(#g-idp)" isAnimationActive={false} connectNulls={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* controls */}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            onClick={() => engine.toggle()}
            className="flex h-9 items-center gap-2 rounded-btn bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
          >
            {snap?.playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {snap?.playing ? "Pause" : "Play"}
          </button>
          <button onClick={() => engine.reset()} className="flex h-9 w-9 items-center justify-center rounded-btn border border-border text-muted-foreground hover:bg-muted" title="Reset">
            <RotateCcw className="h-4 w-4" />
          </button>
          <input
            type="range" min={0} max={1} step={0.001}
            value={snap?.progress || 0}
            onChange={(e) => engine.seekFraction(parseFloat(e.target.value))}
            className="h-1.5 flex-1 min-w-[140px] cursor-pointer appearance-none rounded-full bg-muted accent-primary"
          />
          <div className="flex items-center gap-1 rounded-btn border border-border bg-surface p-1">
            {SPEEDS.map((s) => (
              <button
                key={s}
                onClick={() => engine.setSpeed(s)}
                className={cn("rounded-[6px] px-2 py-1 text-xs font-medium transition-all",
                  (snap?.speed || 1) === s ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}
              >
                {s}×
              </button>
            ))}
          </div>
        </div>

        {/* before/after annotation */}
        {demoInc && (
          <div className="mt-4 flex flex-col gap-3 rounded-btn border border-border bg-surface p-3 sm:flex-row sm:items-center">
            <Badge variant="danger" className="shrink-0">
              <span className="h-1.5 w-1.5 rounded-full bg-danger" /> {demoInc.incident_id}
            </Badge>
            <div className="flex flex-1 flex-wrap items-center gap-x-6 gap-y-1 text-xs">
              <span className="text-muted-foreground">Pipeline detected at <span className="font-mono text-foreground">{fmtTime(demoInc.formation_time)}</span></span>
              <span className="text-muted-foreground">Traditional daily scan: <span className="font-mono text-foreground">{fmtTime(demoInc.traditional_detect_time)}</span></span>
            </div>
            <div className="shrink-0 rounded-btn bg-danger/10 px-3 py-1.5 text-xs font-semibold text-danger">
              Traditional scan misses this for {demoInc.detection_lag_hours}h
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Counter({ icon: Icon, label, value, mono, danger }) {
  return (
    <div className="rounded-btn border border-border bg-surface p-2.5">
      <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Icon className="h-3.5 w-3.5" /> {label}
      </div>
      <div className={cn("mt-0.5 text-lg font-bold", mono && "font-mono text-base", danger && "text-danger")}>{value}</div>
    </div>
  );
}
