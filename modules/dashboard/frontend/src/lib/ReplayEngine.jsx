/**
 * ReplayEngine — drives a virtual clock over the exported replay.json so the Dashboard
 * can animate events arriving and incidents forming in (compressed) real time.
 *
 * NOT a React component — a plain class with subscriber callbacks. The panel subscribes
 * via onTick and re-renders from the emitted snapshot.
 *
 * Speed semantics (critical): "1×" does NOT mean real-time — the active range plays in
 * TARGET_DURATION_S real seconds. Real-time would make a 2-hour window take 2 real hours.
 */
const TARGET_DURATION_S = 120; // active range plays in ~2 real minutes at 1×
const TICK_MS = 100;

export default class ReplayEngine {
  constructor(replay) {
    this.replay = replay;
    this.bins = replay.timeline_bins.map((b) => ({ ...b, ms: Date.parse(b.t) }));
    this.events = replay.events.map((e) => ({ ...e, ms: Date.parse(e.event_time) }));
    this.incidents = replay.incidents
      .map((i) => ({ ...i, ms: Date.parse(i.formation_time) }))
      .sort((a, b) => a.ms - b.ms);

    this.fullStart = Date.parse(replay.meta.t_start);
    this.fullEnd = Date.parse(replay.meta.t_end);
    const dw = replay.meta.demo_window;
    this.demoStart = Date.parse(dw.t_start);
    this.demoEnd = Date.parse(dw.t_end);

    this.range = "demo";
    this.speed = 4;
    this.playing = false;
    this.clock = this.demoStart;
    this._timer = null;
    this._subs = new Set();
  }

  // ----- range / clock bounds
  _start() {
    return this.range === "demo" ? this.demoStart : this.fullStart;
  }
  _end() {
    return this.range === "demo" ? this.demoEnd : this.fullEnd;
  }
  _virtualMsPerTick() {
    const activeDurationS = (this._end() - this._start()) / 1000;
    return (activeDurationS / TARGET_DURATION_S) * this.speed * (TICK_MS / 1000) * 1000;
  }

  // ----- subscriptions
  subscribe(fn) {
    this._subs.add(fn);
    fn(this.snapshot());
    return () => this._subs.delete(fn);
  }
  _emit(newIncidents = []) {
    const snap = this.snapshot(newIncidents);
    this._subs.forEach((fn) => fn(snap));
  }

  snapshot(newIncidents = []) {
    const clock = this.clock;
    let binIndex = -1;
    for (let i = 0; i < this.bins.length; i++) {
      if (this.bins[i].ms <= clock) binIndex = i;
      else break;
    }
    // count events seen within active range only
    const start = this._start();
    let eventsSeen = 0;
    for (const e of this.events) {
      if (e.ms >= start && e.ms <= clock) eventsSeen++;
    }
    const formedIncidents = this.incidents.filter((i) => i.ms <= clock && i.ms >= start);
    return {
      clockTime: new Date(clock).toISOString(),
      clockMs: clock,
      binIndex,
      eventsSeen,
      formedIncidents,
      newIncidents,
      range: this.range,
      speed: this.speed,
      playing: this.playing,
      progress: (clock - start) / (this._end() - start),
    };
  }

  // ----- controls
  play() {
    if (this.playing) return;
    if (this.clock >= this._end()) this.clock = this._start();
    this.playing = true;
    this._timer = setInterval(() => this._step(), TICK_MS);
    this._emit();
  }
  pause() {
    this.playing = false;
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
    this._emit();
  }
  toggle() {
    this.playing ? this.pause() : this.play();
  }
  reset() {
    this.pause();
    this.clock = this._start();
    this._emit();
  }
  seek(ms) {
    this.clock = Math.max(this._start(), Math.min(ms, this._end()));
    this._emit();
  }
  seekFraction(frac) {
    this.seek(this._start() + frac * (this._end() - this._start()));
  }
  setSpeed(mult) {
    this.speed = mult;
    this._emit();
  }
  setRange(range) {
    const wasPlaying = this.playing;
    this.pause();
    this.range = range;
    this.clock = this._start();
    if (wasPlaying) this.play();
    else this._emit();
  }

  _step() {
    const before = this.clock;
    this.clock = Math.min(this.clock + this._virtualMsPerTick(), this._end());
    const newOnes = this.incidents.filter((i) => i.ms > before && i.ms <= this.clock);
    if (this.clock >= this._end()) {
      this.pause();
      this.clock = this._end();
    }
    this._emit(newOnes);
  }

  destroy() {
    if (this._timer) clearInterval(this._timer);
    this._subs.clear();
  }
}
