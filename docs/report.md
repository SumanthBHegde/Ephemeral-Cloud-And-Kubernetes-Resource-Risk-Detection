<!--COVER
title: Ephemeral Cloud & Kubernetes Resource Risk Detection
subtitle: Technical Documentation — Société Générale Hackathon
track: Cloud Security Governance & Risk · Intermediate–Advanced
thesis: A legitimate autoscaler burst and a crypto-mining hijack are statistically identical at the event level. The signal is in the context, not the event — so we detect on context.
project: Sentinel
team: _add team name_
date: June 2026
live: https://sentinel-rho-sooty.vercel.app/app
repo: https://github.com/pavannaik2004/Sentinel
video: _add demo video URL_
-->

# Ephemeral Cloud & Kubernetes Resource Risk Detection

**Technical Documentation — Société Générale Hackathon**
**Track:** Cloud Security Governance & Risk
**Project:** Sentinel — a near-real-time risk-detection pipeline for ephemeral cloud/Kubernetes assets

**🔗 Live demo:** <https://sentinel-rho-sooty.vercel.app/app> · **📹 Demo video:** _add link_ · **Repository:** <https://github.com/pavannaik2004/Sentinel>

---

> **A legitimate autoscaler burst and a crypto-mining hijack are statistically identical at the event level — same API calls, same burst rate. The signal that separates them isn't in the event, it's in the _context_. So we detect on context, not events.**

---

## 1. Executive Summary

Cloud-native enterprises provision hundreds of **ephemeral resources** every day — CI/CD job pods, spot
instances, assumed-role sessions, autoscaled containers — that live for minutes and then vanish.
Traditional controls (quarterly scans, daily inventory syncs) were never built for this tempo, and
attackers exploit exactly that blind spot: a crypto-mining burst can run, profit, and self-destruct
between two daily scans, leaving no asset to investigate.

**Sentinel** is a seven-stage pipeline that discovers ephemeral assets, classifies them, detects
risky transient behavior, correlates related events into incidents, scores risk, and emits
analyst-ready LLM narratives — all visualized in a live SOC console. Its central design insight is that
at the *event* level a benign autoscaler burst and a malicious hijack are indistinguishable; the
separating signal lives in **context** (behavioral cohort, novelty, exposure, cross-source linkage). The
whole system is built to detect on context, not raw events.

Measured against ground-truth labels we control on a 9,857-event synthetic dataset (seed 1337,
reproducible), the pipeline **beats every target in the brief**:

| Brief success criterion | Target | Achieved | Where |
|---|---|---|---|
| Risk-scoring quality (precision) | > 75% | **96% precision@50** (ranked queue) | Risk fusion |
| Detection coverage (recall) | > 70% | **100%** (after correlation) | Correlation |
| Noise reduction (alert reduction) | ≥ 40% | **89%** (4,638 flags → 529 incidents) | Correlation |
| Incident correlation accuracy | High-confidence clusters | **V-measure 0.93** vs `campaign_id` | Correlation |
| Detection latency | Near real-time | Flags **17.9 h before** the next daily scan | Replay |
| Analyst readiness | Single-incident narratives | **263** incidents triaged, **100%** MITRE coverage | LLM triage |

---

## 2. Problem Statement

A cloud-native enterprise runs 500+ Kubernetes workloads and provisions hundreds of ephemeral cloud
resources daily. These assets exist for minutes to hours, then disappear — and every assumption a
traditional security control makes is violated by that lifetime:

| Traditional assumption | Ephemeral reality |
|---|---|
| Assets are stable; inventory can be synced daily | Assets exist for minutes; a daily sync never sees them |
| Each alert maps to a durable resource to investigate | The resource is gone before triage; no forensic evidence remains |
| Identities are long-lived and can be baselined | Sessions have 15-minute TTLs; there is no stable identity to baseline |
| Alert volume is manageable | Autoscaling and CI/CD generate thousands of near-identical events |

**The four real incidents from the brief** frame exactly what the system must catch:

1. **Crypto-mining via a compromised CI/CD account** — 20 spot VMs spun up at 3 AM, terminated before
   the SOC shift began. Cost: **~$14,000 in 90 minutes; zero alerts fired.**
2. **Debug pod with NodePort exposed to `0.0.0.0/0`** — ran 11 minutes, found and exploited by an
   external scanner, dead before any scan could catch it.
3. **Assumed-role session reads PII from S3** — expired in 15 minutes, never correlated to the
   compromised Lambda that triggered it.
4. **Autoscaler burst of 40 pods** — 40 false-positive alerts buried one real credential-abuse alert.

**The pain** is fourfold: asset inventory runs too slowly for minute-long resources; autoscaling/CI noise
creates analyst fatigue; identity/session context is fragmented across cloud, K8s, and IAM logs; and
post-incident forensics are impossible once the resource is gone. **The compliance impact** is direct:
NIST **CM-8** (inventory must include ephemeral assets) and **SI-4** (continuous monitoring of dynamic
workloads), the **CIS Kubernetes Benchmark** (pod security, RBAC, network policy), and **GDPR Art. 32**
(security of processing for ephemeral workloads handling PII).

---

## 3. Challenges Involved — Why This Is Hard

Every hard case in this problem is a pair of look-alikes the system must separate:

- 40 pods in 2 minutes → **HPA autoscale** or **resource hijacking**?
- Spot VM with a public IP and no tags → **misconfigured CI job** or **attacker staging**?
- Assumed-role session hits S3 at 3 AM → **scheduled Lambda** or **compromised credential**?
- Privileged debug pod runs 5 minutes → **developer troubleshooting** or **container escape**?

![Same burst — which is the attack?](figures/confusability.png)

The figure shows two **real populations from our generated data**: a legitimate autoscaler burst and a
crypto-mining hijack. They fire at the **same rate** (left — the `burst_rate` distributions sit directly
on top of each other, mean 10.8 vs 13.9). The only thing that separates them is **context** (right): tag
completeness (0.00 vs 0.54), off-hours timing (0.83 vs 0.08), and untagged spot fleets (0.50 vs 0.00).

**This is the design discipline most submissions skip.** It is trivial to make malicious bursts *bigger*
or *faster* than benign ones — that makes the metrics look great and proves nothing, because it makes the
noise-reduction problem disappear. Our simulator deliberately refuses that shortcut: every malicious
scenario ships a volume- and timing-matched benign twin, differing only in metadata completeness and
ownership. Any system that detects on event volume alone fails on exactly the ambiguous cases this
project exists to solve.

The confusability figure is the three-feature teaser for one scenario pair. The same effect holds across
**all eight context features and the entire dataset** (8,147 benign vs 1,710 risky events):

![Context features separate risky from benign; burst volume does not](figures/feature_separation.png)

`burst_rate` (top-left) barely moves between benign and risky — that's the trap a volume detector falls
into. Tag completeness, off-hours timing, exposure window, and cohort-deviation carry the separation.

There is a second dimension of difficulty: **time**. A daily scan inspects the environment once every 24
hours, but the densest crypto incident in our data (INC-0230) forms and self-destructs in under an hour —
a **traditional scan misses it for 17.9 hours**, by which point the spot fleet is terminated and the
evidence is gone. Detection latency must be shorter than the resource lifetime, not the scan interval.

**The conclusion that drives every design decision: detect on context, not events.**

---

## 4. Proposed Solution

Sentinel is a single pipeline that follows the brief's prescribed order literally:
`ingest → enrich → detect → cluster → score → LLM narrative → dashboard`. Rather than picking one of the
brief's three approach tiers, it **merges all three into one pipeline**:

- **Option A (ML + LLM)** is the spine — an unsupervised anomaly ensemble feeds an LLM triage agent.
- **Option B (statistical baselines)** folds in as a cheap pre-filter — cohort-relative deviation
  scoring suppresses what is normal for an identity's behavioral cohort.
- **Option C (deterministic rules)** folds in as always-on tripwires — they force a severity floor
  regardless of the ML score, so the headline danger signals are caught even before any model runs.

They are inputs to one pipeline, not three separate tiers. The architecture is built around **four
differentiators** (§6) and one non-negotiable ordering rule: **risk is scored at the incident level,
after clustering** (§6).

**Framework alignment.** The solution maps directly onto the governance frameworks named in the brief:

| Framework | Controls addressed |
|---|---|
| **NIST SP 800-53** | CM-8 (component inventory of ephemeral assets), SI-4 (system monitoring), IR-4 (incident handling) |
| **MITRE ATT&CK** | T1496 (Resource Hijacking), T1578 (Modify Cloud Compute Infra), T1190 (Exploit Public-Facing App), T1610 (Deploy Container), T1078 (Valid Accounts) |
| **CIS Kubernetes Benchmark** | privileged-container and network-exposure controls (encoded as tripwire rules) |
| **GDPR Art. 32** | security of processing — the PII-exfiltration incident (INC-C) is detected and triaged |

---

## 5. Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Language / data | Python 3.12, Pandas, NumPy/SciPy, PyArrow + Parquet | Tabular pipeline; every stage persists to Parquet for 1:1-joinable, inspectable artifacts |
| Anomaly detection | scikit-learn `IsolationForest` (primary) + PyOD `ECOD` (second vote) | Unsupervised, label-free, deterministic; ~10k×8 tabular is IsolationForest's sweet spot; ECOD adds a parameter-free independent view |
| Calibration | scikit-learn `IsotonicRegression` + `StratifiedKFold` | Turns the raw score into a true probability via out-of-fold calibration (no leakage) |
| Correlation | NetworkX | Event-node graph with time-gated typed edges; incidents = connected components |
| LLM triage | OpenAI `gpt-4o-mini`, strict `json_schema` structured output | Forces validated structured JSON (intent, MITRE, guardrails), not free prose; cached for an offline demo |
| Dashboard | React 19 + Vite + Tailwind v3 + Recharts | SOC console fed by static JSON; no live model in the demo path |
| Figures / eval | matplotlib, pytest (50 tests) | Every figure regenerates from the same Parquet; metrics gated by tests |

The model choice was deliberate. A supervised model (e.g. TabPFN) was **rejected** because it forces a
train/test split and label leakage on a problem whose whole point is unsupervised separation; a
PyTorch/Keras autoencoder was **rejected** as overkill for a 10k×8 table. The IsolationForest + ECOD
ensemble gives two independent unsupervised views with no training loop and no label exposure.

---

## 6. Architecture

```mermaid
flowchart TD
    CT[Cloud audit<br/>CloudTrail]:::src --> S1
    K8[K8s audit<br/>audit.k8s.io]:::src --> S1
    IDP[Identity / session<br/>IdP]:::src --> S1
    S1[1 · Ingest + enrich<br/><small>unified schema · behavioral cohorts · context features</small>] --> S2
    S2[2 · Detect<br/><small>tripwires + recall-first anomaly ensemble (IF + ECOD) + cohort suppression</small>] --> S3
    S3[3 · Cluster<br/><small>NetworkX entity graph · incidents = connected components (id + ns + time)</small>] --> S4
    S4[4 · Score<br/><small>fused, isotonic-calibrated risk — at the INCIDENT level, AFTER clustering</small>] --> S5
    S5[5 · LLM triage<br/><small>validated structured JSON: intent · confidence · MITRE · guardrails</small>] --> S6
    S6[6 · Dashboard<br/><small>React SOC console fed by static JSON — offline, demo needs no network</small>]
    classDef src fill:#f3f4f6,stroke:#111827;
```

![Pipeline architecture](figures/architecture.png)

### The four differentiators

1. **Behavioral cohorts replace per-identity baselines.** Ephemeral identities have no stable history,
   so we cluster principals into cohorts (`ci_runner`, `hpa_autoscaler`, `human_dev`,
   `scheduled_lambda`) and baseline the *cohort*. A brand-new pod inherits its cohort's baseline
   instantly — converting the brief's stated blocker ("no stable identity to baseline") into the
   solution's strongest signal.

2. **Two-stage detection separates recall from precision.** Stage 1 is a recall-first anomaly ensemble
   (IsolationForest + ECOD) where over-flagging is expected. Stage 2 suppresses candidates that are
   normal *for their cohort*. This is how high recall and meaningful alert reduction are achieved
   simultaneously instead of being traded against each other.

3. **Graph correlation surfaces campaigns time-windowing cannot.** A NetworkX graph with time-gated,
   typed edges links related events across all three sources. This collapses 40 autoscaler alerts into 1
   incident and recovers the Lambda → assumed-role session → S3 chain that occurs over minutes and across
   log boundaries.

4. **The LLM is a triage agent, not a prose generator.** It returns *validated structured JSON* (intent,
   confidence, MITRE techniques, guardrails) under a strict schema with retry and a templated fallback.
   Responses are cached so the live demo never depends on a network call.

### The critical ordering catch — score *after* clustering

Three individually low-scoring events from the same principal in the same five-minute window can be one
high-severity incident *together*. Per-event scoring before clustering misses that. Risk scoring
therefore happens at the **incident level, after correlation** — never before. Reordering these stages
would break the system on exactly the ambiguous cases it exists to solve.

---

## 7. The Modules — Stage by Stage

Each module is an independent stage that reads the previous stage's Parquet and writes its own. This
section walks them in order; the code snippets are taken verbatim from the implementation.

### 7.1 Data Simulation — `modules/data_simulation`

*Deliverable: working prototype on simulated logs + a short data dictionary.*

There is no provided dataset, so the generator produces three labeled, synthetic log streams —
**9,857 events over a 5-day span, fixed seed 1337** — grounded field-by-field in real AWS CloudTrail,
`audit.k8s.io/v1`, and Okta-style IdP record formats. It is built **ground-truth-first**: the real
incident structure (which events belong to one crypto burst, which pod is the debug pod) is constructed
first, then every record is derived from it. Detection signals live exactly where they do in production
telemetry — in the **metadata**: missing tags, an absent `ownerReferences`, a `privileged` security
context, off-hours timing.

A hint of the data — one abridged CloudTrail `RunInstances` record (the full nested AWS / Kubernetes /
Okta fields are kept authentic in the real streams):

```json
{
  "eventName": "RunInstances",
  "eventTime": "2026-06-18T03:14:07Z",
  "userIdentity": { "type": "AssumedRole",
    "arn": "arn:aws:sts::123456789012:assumed-role/ci-runner-role/ci-deploy" },
  "sourceIPAddress": "203.0.113.7",
  "requestParameters": { "instanceType": "g4dn.xlarge",
    "instanceMarketOptions": { "marketType": "spot" }, "tagSpecificationSet": {} },
  "responseElements": { "instancesSet": { "items": [
    { "instanceId": "i-0ab12cd34ef56", "networkInterfaceSet": { "publicIp": "203.0.113.7" } } ] } },
  "sharedEventID": "127e10d3-1287-5370-cf67-7e19c7f37e4a"
}
```

The hardest design principle — **confusability** — is enforced in code. Every malicious scenario emits a
benign twin of the **same burst size and timing offsets**, differing only in metadata:

```python
def _malicious(ctx, pair_id, n, *, incident_id=None, anchor=None):
    cohort = "ci_runner"
    # ... burst of n RunInstances, off-hours, spot, public IP, NO tags:
    add_event(camp, source=SRC_CLOUDTRAIL, action="RunInstances", ...,
              attrs={"instance_type": ctx.rng.choice(_MINING_TYPES), "spot": True,
                     "public_ip": public_ip(ctx.rng), "tags": {},  # deliberately untagged
                     ...})

def _benign_twin(ctx, pair_id, n, region):
    cohort = "hpa_autoscaler"
    offs = burst_offsets(ctx, n, 2, 9)   # SAME burst size & offset distribution as the twin
    add_event(camp, source=SRC_CLOUDTRAIL, action="RunInstances", ...,
              attrs={"instance_type": ctx.rng.choice(_NORMAL_TYPES), "spot": False,
                     "public_ip": None, "tags": gen_tags(ctx, cohort),  # fully tagged
                     ...})
```

A 16-check validator gates the dataset (per-source schema validity, anomaly-mix tolerance, confusability
pairing, cross-source linkage recoverable from authentic fields alone, all four canonical incidents
present). The realized anomaly mix matches the brief — ~17% risky across crypto-burst, public-exposure,
identity-anomaly, legit-autoscale, legit-CI/CD, and routine traffic. **Data dictionary (abridged):**

| Source | Records | Key fields |
|---|---|---|
| `cloudtrail.jsonl` (AWS CloudTrail) | 4,000 | `eventName`, `userIdentity`/`sessionContext`, `sourceIPAddress`, `requestParameters` (instanceType, tags, spot), `responseElements` (public IP), `sharedEventID` |
| `k8s_audit.jsonl` (`audit.k8s.io/v1`) | 4,357 | `verb`, `objectRef` (namespace/resource), `user.username`, `ownerReferences` (absence = bare pod), `securityContext.privileged`, NodePort source ranges |
| `idp_session.jsonl` (Okta System Log) | 1,500 | `eventType`, `actor.alternateId`, `authenticationContext.externalSessionId`, `client.ipAddress`, `outcome.result` |

The full field-level dictionary is committed at [`data/raw/data_dictionary.md`](../data/raw/data_dictionary.md).
Ground-truth labels are held in a **separate sidecar used only for measurement** — described in §9 and
never read by the detection path.

### 7.2 Ingest & Enrich + Ephemeral Classifier — `modules/ingest_enrich`

*Deliverable: ephemeral classifier explained clearly.*

This stage normalizes all three sources into one unified event schema, then assigns each principal to a
**behavioral cohort** and computes the eight context features (burst rate, novelty, tag completeness,
privilege, exposure, off-hours, cohort-deviation). Cohort assignment is rule-assisted (no ML), using
authentic identity signals in priority order — K8s service-account → CloudTrail role/service → IdP email
prefix → source-IP CIDR:

```python
def resolve(self, row: dict) -> str:
    source, pid = row.get("source"), row.get("principal_id") or ""
    if source == "k8s_audit":
        hit = _K8S_SUBJECTS.get(pid)            # e.g. ...:ci-runner-sa -> ci_runner
        if hit: return hit
    elif source == "cloudtrail":
        role = row.get("role_name")
        if role in _ROLE_NAMES: return _ROLE_NAMES[role]
        if pid.startswith("service:"):          # autoscaling.amazonaws.com -> hpa_autoscaler
            for token, name in _INVOKED_BY.items():
                if token in pid: return name
    elif source == "idp_session":
        prefix = pid.split("@")[0].rsplit("-", 1)[0]
        if prefix in _IDP_PREFIXES: return _IDP_PREFIXES[prefix]
    return self._by_cidr(row.get("source_ip")) or UNKNOWN   # never silently forced
```

Principals matching no known cohort become **`unknown`** — *itself a signal*, not silently forced into
the wrong baseline.

![Behavioral cohorts — size vs risky fraction](figures/cohort_risk.png)

The `unknown` cohort is the proof: all 629 of its events are the identity-anomaly attack (**100% risky**).
"Fits no cohort baseline" is not noise to clean up — it *is* the detection signal. Cohort accuracy on the
9,228 recognizable principals is 100%.

### 7.3 Detection — `modules/detection`

*Deliverable: detection rules / ML approach explained clearly.*

Detection is two-stage with an always-on rule layer. **Tripwires** are deterministic checks that force a
HIGH severity floor and are *never* suppressed — including the context tripwire `cohort == unknown`:

```python
def apply_tripwires(df):
    nodeport_open  = df["public_exposure_flag"].fillna(0.0) >= 1.0       # NodePort 0.0.0.0/0
    bare_priv      = df["controller_owner"].isna() & df["privileged"].fillna(False)
    burst          = df["burst_rate"].fillna(0) > BURST_TRIPWIRE          # > 10 in 5 min
    broad          = df["broad_rbac"].fillna(False)                       # cluster-admin / wildcard
    unknown_cohort = df["cohort"].eq("unknown")                           # fits no baseline = signal
    hit = nodeport_open | bare_priv | burst | broad | unknown_cohort
    df["tripwire_hit"], df["severity_floor"] = hit, hit.map({True: "HIGH", False: "NONE"})
    return df
```

**Stage 1** is a recall-first unsupervised ensemble — two label-free detectors vote and their
min-max-normalized scores are averaged. Over-flagging here is intentional:

```python
iforest = IsolationForest(n_estimators=200, contamination=0.30, random_state=1337)
iforest.fit(X);  if_raw = -iforest.decision_function(X)     # higher == more anomalous
ecod = ECOD();   ecod.fit(X);  ecod_raw = ecod.decision_scores_
df["ensemble_score"] = (_minmax(if_raw) + _minmax(ecod_raw)) / 2.0
df["is_candidate"]   = df["ensemble_score"] >= df["ensemble_score"].quantile(0.65)
```

**Stage 2** wins precision back with no ML, suppressing a candidate only when it is normal *for its
cohort* on every axis — and never suppressing a tripwire:

```python
cohort_normal = known_cohort & in_distribution & tags_ok & in_hours & not_tripwire
df["is_suppressed"]    = df["is_candidate"] & cohort_normal
df["predicted_risky"]  = (df["is_candidate"] & ~df["is_suppressed"]) | df["tripwire_hit"]
```

![Anomaly-model output — benign vs risky score distributions](figures/ensemble_scores.png)

The ensemble shifts risky events to higher scores, but — honestly — the populations *overlap*. That
overlap is the confusability thesis in action, not a model failure: the right tail is clearly more risky,
but the ambiguous middle is exactly what cohort suppression and graph correlation resolve downstream.

### 7.4 Correlation — `modules/correlation`

*Deliverable: correlate related events into incidents to reduce alert noise.*

Correlation builds an **event-node graph with time-gated, typed edges**, each enforcing the
identity + namespace + time envelope *at edge-creation time* (an entity-node graph cannot — one timeless
`replicaset-controller` node would chain every autoscaler burst, across all namespaces and all time, into
one mega-incident). Five edge rules, grounded in the actual linkage values:

```python
EDGE_SPECS = (
    EdgeSpec("same_principal",   ("principal_id", "ns_part"), TIME_WINDOW_S),   # 30 min, ns-partitioned
    EdgeSpec("same_session",     ("session_name",),           TIME_WINDOW_S),   # only link IdP->AssumeRole
    EdgeSpec("external_session", ("external_session_id",),    TIME_WINDOW_S),
    EdgeSpec("shared_event",     ("shared_event_id",),        None),            # UUID, safe ungated
    EdgeSpec("same_resource",    ("resource_id", "principal_id"), RESOURCE_WINDOW_S),  # 2 h, create->terminate
)
```

Incidents are connected components seeded from flagged events with one-hop bridge expansion. This both
collapses noise **and recovers missed detections** — benign bridge events one hop from a flagged seed
pull the missed true positives back in (recall climbs 84% → 100%).

![Cross-source correlation of one incident](figures/graph_incident.png)

This is the payoff time-window clustering cannot reach: an IdP login, an `AssumeRoleWithWebIdentity`, and
three S3 `GetObject` calls — one session, two log sources, minutes apart — recovered as a single incident.

### 7.5 Risk Fusion — `modules/risk_fusion`

*Deliverable: assign risk scores at resource and incident levels.*

Fusion computes a **label-free** event-level raw risk as a fixed-weight sum of the §5 signals (weights
0.30/0.25/0.20/0.10/0.15, summing to 1.0 — expert constants, not learned):

```python
WEIGHTS = {"anomaly": 0.30, "signal": 0.25, "exposure": 0.20, "privilege": 0.10, "novelty": 0.15}
df["raw_risk"] = (WEIGHTS["anomaly"] * anomaly + WEIGHTS["signal"] * signal
                  + WEIGHTS["exposure"] * exposure + WEIGHTS["privilege"] * privilege
                  + WEIGHTS["novelty"] * novelty)
```

The raw score is then calibrated to a probability via **out-of-fold isotonic regression** — the *one
sanctioned label touch* in the entire pipeline. `StratifiedKFold` prevents a positive-starved fold from
fitting a degenerate curve, and out-of-fold prediction means no event is ever scored by a model that saw
its label:

```python
def oof_calibrate(raw_risk, y):
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=1337)
    for train_idx, test_idx in skf.split(x, y):
        ir = IsotonicRegression(out_of_bounds="clip").fit(x[train_idx], y[train_idx])
        p[test_idx] = ir.predict(x[test_idx])     # no row scored by a model that saw it
    return p
```

Finally, member probabilities aggregate to an incident `risk_score = 0.7·max + 0.3·mean` (one decisive
event dominates, mean dampens noise), with a tripwire severity floor and CRITICAL/HIGH/MEDIUM/LOW bands.

![Risk calibration — predicted vs observed](figures/calibration.png)

Calibration is near-perfect: across ten event bins the predicted probability tracks the observed risky
rate with a maximum deviation of **0.016**. A `p_event` of 0.8 really does mean ~80% likely-malicious.

### 7.6 LLM Triage — `modules/llm_triage`

*Deliverable: analyst-ready incident narratives with evidence, intent, MITRE, and remediation.*

The LLM is a **triage agent**, not a prose generator. For each CRITICAL/HIGH incident it is handed an
evidence bundle and asked for a **strict 7-field JSON** object — `additionalProperties: False` plus
all-required is what makes `strict: true` enforce the shape:

```python
TRIAGE_SCHEMA = {
    "name": "incident_triage", "strict": True,
    "schema": {"type": "object", "additionalProperties": False,
        "required": ["likely_intent", "confidence", "mitre", "key_evidence",
                     "disambiguation", "recommended_guardrails"],
        "properties": { "likely_intent": {"type": "string"}, "confidence": {"type": "number"},
                        "mitre": {"type": "array", "items": {"type": "string"}}, ... }}}
```

Even with a strict schema, the output is re-validated (MITRE id format `T\d{4}(\.\d{3})?`, non-empty
lists) and retried with exponential backoff; on persistent failure the stage degrades to a deterministic,
**label-free** template so it never crashes:

```python
for attempt in range(MAX_RETRIES):
    try:
        resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages,
                   response_format={"type": "json_schema", "json_schema": TRIAGE_SCHEMA}, temperature=0)
        return validate_triage(json.loads(resp.choices[0].message.content))
    except (ValidationError, json.JSONDecodeError, Exception) as err:
        last_err = err
    if attempt < MAX_RETRIES - 1: time.sleep(2 ** attempt)   # 1s, 2s backoff
```

Responses are cached per incident (existence-based reuse, so reruns cost **$0** and the demo is offline).
All **263** CRITICAL/HIGH incidents were triaged live via `gpt-4o-mini` (mean confidence 0.852, **100%
MITRE coverage**).

### 7.7 Dashboard — `modules/dashboard`

*Deliverable: dashboard with ephemeral inventory/TTL, creation spikes, top risky resources/identities,
and an incident list with narratives.*

The SOC console ("Sentinel", React 19 + Vite + Tailwind) is fed by **static JSON** exported from the
pipeline — no live model or LLM call in the demo path, so it runs fully offline. It maps the brief's
dashboard deliverable panel-for-panel:

- **Ephemeral inventory & TTL distribution** + **creation-spike timeline** (events per 15-min bin)
- **Top risky resources / identities / namespaces / cohorts** (ranked)
- **Risk Findings** — a ranked incident queue with a **triage drawer** (intent, confidence, MITRE,
  evidence, disambiguation, recommended guardrails, top member events) — the **incident list with
  narratives**
- **Alert-fatigue funnel** (9,857 → 3,517 → 3,167 → 529 → 263)
- **Live replay simulation** — the headline feature: plays the 5-day event stream against a virtual
  clock, forming incidents live and contrasting pipeline detection time against the next daily scan
  ("Traditional scan misses this for 17.9h")
- A **guided tour** (driver.js) for judges and an **AI Risk Analyst** chat grounded in the cached triage

![Sentinel — dashboard overview (KPIs · replay · alert-fatigue funnel)](figures/ui_dashboard.png)

![Sentinel — Risk Findings queue + triage drawer (incident narrative)](figures/ui_findings.png)

Live console: <https://sentinel-rho-sooty.vercel.app/app>.

---

## 8. Sample Incidents

*Deliverable: 2–3 sample incidents with evidence, MITRE mapping, and recommended guardrails.* Each is a
real, recovered incident from the pipeline, triaged by the Stage-5 agent.

### INC-A — Crypto-mining via a compromised CI/CD account

- **Evidence:** 20× `RunInstances` by `ci-runner-sa` at ~03:14 (off-hours), spot instances, public IPs
  assigned, **tags empty**, GPU/compute instance types (`g4dn.xlarge`, `c5.4xlarge`); 20× matching
  `TerminateInstances` ~90 min later (track-covering). Cohort `ci_runner`, `tag_completeness = 0.00`,
  `off_hours_flag = 1`, `burst_rate > 10` → tripwire fires. 40 raw alerts collapse to **1 incident**.
- **MITRE:** **T1496** (Resource Hijacking), **T1578.002** (Modify Cloud Compute Infrastructure — Create
  Instance).
- **Recommended guardrails:** an SCP denying `RunInstances` without a mandatory `Owner`/`Env` tag set;
  deny public-IP assignment on spot fleets launched by CI roles; alert on off-hours `RunInstances` by
  service accounts; budget/anomaly guard on sudden GPU-instance spend.

### INC-B — Debug pod with NodePort exposed to `0.0.0.0/0`

- **Evidence:** a bare pod (**no `ownerReferences`** → `controller_owner = None`), `privileged: true`
  security context, a NodePort service exposed to `0.0.0.0/0`, lifetime ~11 minutes. Two tripwires fire
  simultaneously (bare-privileged pod + open NodePort); 3 raw events → **1 incident**.
- **MITRE:** **T1610** (Deploy Container), **T1190** (Exploit Public-Facing Application).
- **Recommended guardrails:** an admission policy (OPA/Kyverno) barring privileged pods without a
  controller owner; deny `Service`/NodePort with `0.0.0.0/0` source ranges; enforce a default-deny
  NetworkPolicy per namespace; short-TTL eviction for controllerless pods.

### INC-C — Compromised assumed-role session reads PII from S3

- **Evidence:** a federated IdP login → `AssumeRoleWithWebIdentity` → three S3 `GetObject` calls on a PII
  key prefix at ~03:00, no scheduled-trigger context, session TTL 15 min. Spans **two log sources** (IdP
  + CloudTrail); recovered as one incident via `same_session` / `external_session` / `shared_event`
  edges — the cross-source chain a time-window clustering cannot reconstruct (see Figure in §7.4). 7
  events → **1 incident**.
- **MITRE:** **T1078** (Valid Accounts), **T1530** (Data from Cloud Storage Object).
- **Recommended guardrails:** shorten STS session TTLs and scope role policies to least privilege; alert
  on off-hours PII-prefix `GetObject` by federated sessions; require correlation of every assumed-role
  session back to its originating IdP login; enable S3 access-point and Block Public Access guards on PII
  buckets.

---

## 9. Results & Evaluation

Every metric is computed against a **held-out ground-truth sidecar** (`labels.jsonl`), one row per event:
`is_risky` (0/1), `scenario_type`, `cohort`, and `campaign_id` (shared across all events of one
campaign, across all three sources). These labels are used **only to measure** — never to predict. The
one place a label is read inside the pipeline is the out-of-fold calibration of §7.5, where no event is
scored by a model that saw its own label.

### The deliverable scorecard

Measured the way a SOC actually consumes the output — a **ranked incident queue worked top-down** —
Sentinel beats every target in the brief:

| Metric (the deliverable) | Target | Achieved |
|---|---|---|
| Risk-scoring quality — **precision@50** (ranked queue) | > 75% | **96%** |
| Detection coverage — **recall** | > 70% | **100%** |
| Noise reduction — **alert reduction** | ≥ 40% | **89%** (4,638 flags → 529 incidents) |
| Incident-correlation accuracy — V-measure vs `campaign_id` | high-confidence | **0.93** (homogeneity 0.88 / completeness 0.99) |
| Risk calibration | predicted ≈ observed | max deviation **0.016** |

**Risk-scoring quality is measured as precision@K** — the brief's prescribed metric — because that is how
the result is used: an analyst opens the highest-risk incidents first. Precision stays high at the top of
the ranked queue: **90% @10, 95% @20, 96% @50**.

![Risk-ranking quality — precision / recall @ K](figures/precision_at_k.png)

### Why is flag-set precision lower in the ablation below?

Because graph correlation *deliberately* trades event-level precision for recall. To reach **100% recall**
it pulls in benign "bridge" events sitting one hop from a flagged seed — recovering the true positives the
anomaly model missed. That inflates the raw flag set, so **flag-level** precision dips, and is then
**recovered by ranking incidents**, not by the flag set. The ablation table shows that mechanism stage by
stage; its precision column is the *flag-set view*, while the **deliverable precision is the 96% @50
above**. Each row adds exactly one differentiator, proving each earns its place:

| Configuration (mechanism view) | Precision (flag set) | Recall | Alert reduction |
|---|---:|---:|---:|
| Tripwires only | 43.5% | 72.5% | 38% |
| + Stage-1 anomaly ensemble | 31.1% | 84.2% | 0% |
| + Stage-2 cohort suppression | 33.6% | 84.2% | 8% |
| + Graph correlation (recall → 100%) | 24.1% | **100%** | **89%** |
| + Risk fusion (conservative band ≥ HIGH cut) | 68.4% | 99.5% | 89% |
| **→ Risk fusion, ranked queue (precision@50)** | **96%** | — | 89% |

![Ablation — each differentiator earns its place](figures/ablation.png)

The penultimate row (68.4%) is the deliberately high-recall **band cut** — by design a tripwire incident
is never silently dismissed. The final row is how the result is actually consumed: the **ranked queue**,
precision@50 = **96%**.

![Alert-fatigue funnel](figures/alert_funnel.png)

**Canonical incident recovery:** INC-A 40 alerts → 1 incident; INC-B 3 → 1; INC-C 7 → 1 (spanning
CloudTrail + IdP); INC-D correctly keeps the buried credential-abuse alert as its own HIGH incident while
collapsing the surrounding noise.

The self-evaluation is computed directly against the labels, exactly as the brief prescribes:

```python
# Recall + alert reduction — the brief's self-eval, on the flag set
y_true, y_pred = labels["is_risky"], labels["predicted_risky"]
print(f"Recall: {recall_score(y_true, y_pred):.0%}")                  # 100% after correlation
raw = int(y_pred.sum())
inc = labels.loc[y_pred == 1, "incident_id"].nunique()
print(f"Alert reduction: {raw} -> {inc} ({(1 - inc/raw)*100:.0f}%)")  # 4638 -> 529  (89%)

# Risk-scoring quality — precision@K on the ranked incident queue (how a SOC consumes it)
ranked = incidents.sort_values("risk_score", ascending=False)
for k in (10, 20, 50):
    print(f"precision@{k}: {precision_at_k(ranked, k):.0%}")          # 90% / 95% / 96%
```

### 9.1 Honest evaluation — questions a judge should ask

**"Isn't detecting `cohort = unknown` just detecting a label you injected?"** No. Confusability is
enforced at *generation* time (§3) — benign and malicious bursts are statistically indistinguishable in
volume/rate. The fusion score is **label-free**; the only sanctioned label touch is out-of-fold isotonic
calibration, where no event is scored by a model that saw its label. We detect the *behavior*; the label
is downstream ground truth used to *measure*, not to predict.

**"Precision is 68%, but the target was 75%."** 68.4% is the deliberately high-recall **band cut**
(`band ≥ HIGH`) — by design, a tripwire incident is never silently dismissed. The brief's actual
risk-scoring-quality metric is **precision/recall@K**, where the ranked queue an analyst works top-down
hits **96% @50**.

**"It's all synthetic."** Controlled, not faked. No public dataset carries the labeled ground truth
(`is_risky`, `campaign_id`, `severity`) this problem requires; the simulator is grounded field-by-field
in real AWS/Kubernetes/Okta schemas and real burst-timing distributions, and every metric is measured
against labels constructed ground-truth-first.

---

## 10. Scalability

The pipeline is designed to scale from the demo's 10k events to production volume without architectural
change:

- **Stateless, per-stage Parquet handoff.** Each stage is a pure transform reading one table and writing
  another, so stages parallelize and the slow ML stages run offline/batch.
- **Streaming-ready.** The replay path already consumes events one-at-a-time; the batch Parquet source
  swaps for a stream (Kafka/Kinesis) with the same normalize + cohort logic per event. Windowed features
  stay micro-batch.
- **Cohort baselines are cheap and precomputed.** A new ephemeral identity inherits its cohort baseline
  instantly — there is no per-identity model to train, so identity cardinality does not blow up state.
- **Graph memory is bounded by the envelope.** Correlation never builds a global graph; the
  identity + namespace + time window caps each connected component, so memory scales with *concurrent*
  activity, not total history. Work shards naturally by namespace and time window.
- **LLM cost/latency is bounded.** Triage runs only on CRITICAL/HIGH incidents (263 of 9,857 events),
  is cached existence-based (reruns cost $0), and is async-batchable.

---

## 11. Bottlenecks & Challenges Faced

The hard engineering problems during the build — and how each was resolved — are themselves the proof
the design is non-trivial:

- **The anomaly ensemble alone plateaued at ~47% recall.** The `identity_anomaly` attack is a *dense,
  same-shape cluster*, not a sparse outlier, so IsolationForest/ECOD structurally cannot flag it. Adding
  the **context tripwire `cohort == unknown`** lifted recall to 84%, and graph correlation to 100% — the
  thesis made literal: detect on context, not events.
- **A naïve entity graph produced one mega-incident.** A timeless `replicaset-controller` principal node
  chained every autoscaler burst across all namespaces and time. Fixed by **inverting to an event-node
  graph** and moving the temporal gate to *edge creation*, making the identity+namespace+time envelope a
  structural property.
- **Calibration folds went degenerate at a 17% positive rate.** Plain K-fold occasionally fit an isotonic
  curve on a positive-starved fold. Fixed with **`StratifiedKFold`**, keeping ~17% positives per fold.
- **The paid LLM API could be re-spent on every rerun.** Fixed with an **existence-based cache** — once an
  incident's triage JSON exists, the model is never re-called, so reruns and the live demo cost $0.
- **Optional heavy deps (`pyod`, `openai`) threatened the demo path.** Both are **lazy-imported**, and the
  dashboard build avoids the detector's import graph entirely, so the offline console runs without them.

---

## 12. Future Enhancements

- **Real-stream ingest** — wire the normalize/cohort path to a live Kafka/Kinesis feed for true
  near-real-time detection on production telemetry.
- **Online / streaming cohort learning** — discover and update cohorts continuously instead of from a
  fixed config, so new workload archetypes form their own baselines automatically.
- **Analyst feedback loop** — capture SOC true-positive/false-positive verdicts and feed them back into
  the suppression thresholds (and, eventually, learned fusion weights instead of fixed expert constants).
- **A third anomaly vote** — add an autoencoder or copula-based detector as an independent third opinion
  for the hardest ambiguous middle.
- **Multi-cloud adapters** — Azure Activity Log and GCP Audit Log schema adapters behind the same unified
  event schema.
- **Live, guardrailed LLM tool use** — let the triage agent pull additional evidence via validated tools
  while keeping the strict-schema output contract.

---

## 13. Reproducibility

The full pipeline is deterministic (fixed seed 1337) and reproducible end-to-end:

```bash
pip install -r requirements.txt

python -m modules.data_simulation.generator.build   # generate data/raw/
python -m modules.ingest_enrich.build               # → events_enriched.parquet
python -m modules.detection.build                   # → detections.parquet
python -m modules.correlation.build                 # → incidents.parquet
python -m modules.risk_fusion.build                 # → incidents_scored.parquet
python -m modules.llm_triage.build --no-llm         # → incidents_triaged.parquet (offline)
python -m modules.dashboard.build                   # → frontend/public/data/*.json
python -m modules.dashboard.figures.build_all       # → docs/figures/*.png (every figure in this report)

python -m pytest tests/ -q                          # 50 passed

cd modules/dashboard/frontend && npm install && npm run dev   # http://localhost:5173/app
```

The dashboard reads **static JSON** exported from the pipeline — no live model or LLM call in the demo
path, so it runs fully offline. The LLM triage (`gpt-4o-mini`) is pre-generated and cached; the
`--no-llm` path and the entire test suite need no API key. Every figure in this report regenerates from
the same Parquet artifacts via `build_all` — none are hand-drawn or mocked.

---

## Appendix

- **Full data dictionary:** [`data/raw/data_dictionary.md`](../data/raw/data_dictionary.md)
- **Design source of truth:** [`docs/ephemeral_risk_detection_analysis.md`](ephemeral_risk_detection_analysis.md)
- **Test suite:** 50 tests (6 Stage 0 · 9 Stage 1 · 8 Stage 2 · 8 Stage 3 · 9 Stage 4 · 10 Stage 5)
- **Repository layout:** `modules/{data_simulation, ingest_enrich, detection, correlation, risk_fusion, llm_triage, dashboard}`, `data/{raw, processed}`, `docs/`, `tests/`

---

**🔗 Live demo:** <https://sentinel-rho-sooty.vercel.app/app> · **📹 Demo video:** _add link_ · **Repository:** <https://github.com/pavannaik2004/Sentinel>
