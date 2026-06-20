# Stage 3 — Graph Correlation

Clusters Stage-2 detection flags into **incidents** by building an entity graph and taking its
connected components. This is where the headline **alert reduction** is won (40 autoscaler alerts
→ 1 incident) and where cross-source chains time-window clustering cannot recover — IdP login →
assumed-role session → S3 read — become a single traced incident.

**Input:** `data/processed/detections.parquet` (Stage 2 — enriched events + `predicted_risky`,
`ensemble_score`, `severity_floor`, `tripwire_hit`, `is_candidate`).
**Output:**
- `data/processed/incidents.parquet` — one row per incident (primary input to risk_fusion).
- `data/processed/event_incidents.parquet` — every event's `record_id → incident_id`
  (`None` for the ~8k events in no incident; risk_fusion's timeline + the dashboard need them all).

Clustering only — risk **scoring happens after clustering** (the next stage), per the
non-negotiable ordering catch (design doc §3).

## Run

```bash
python -m modules.correlation.build       # detections.parquet -> incidents.parquet (+ event map)
python -m modules.correlation.evaluate    # alert reduction + correlation accuracy + ablation
python -m pytest tests/test_stage3.py -q
```

## Graph model — Deliberate inversion of design §8 to enforce the envelope

### Design §8 vs Implementation

**Design §8 specifies:** entity multigraph (principals, sessions, resources, namespaces as nodes;
events as edges carrying linkage metadata).

**Implementation uses:** event multigraph (events as nodes; shared entities as **typed, time-gated
edges**, carrying the linkage key and timing).

### Why the inversion

The identity+namespace+time **envelope** (design doc §18) must be enforced to prevent the envelope
constraint from becoming a dead letter. One service account (`replicaset-controller`) triggers
every autoscaler burst in the cluster. Under the §8 entity model, this yields one timeless
`principal` node; all bursts (web, prod, tomorrow, next week) touching this principal would
**chain into one mega-incident** because a node has no temporal scope. The envelope constraint
would be *stated* (in docstrings) but not *enforced* (by the graph structure).

The event-node inversion enforces the envelope **at build time**: edges exist only between events
within a time window *and* in the same namespace (cloud events have no namespace, so they group by
identity alone). The invariant **every edge must have ≥1 seed endpoint** (enforced in
`build_graph.py`) further prevents bridge-bridge chains that could leak across the envelope
(2-hop expansion).

### Output equivalence

The connected-component result is **functionally identical** to the §8 entity model whenever no
time gating would apply (i.e. all events are within the window). The incident artifact still
surfaces the entity view: `principal_ids`, `namespaces`, `resource_ids`, `edge_types` are
reconstructed per-component from the member events' columns. Cross-source chains (IdP → STS → S3)
work identically. The trade-off is **implementation complexity vs correctness**: the event model
is more complex to reason about, but the envelope actually holds.

### Edge rules (grounded in the actual linkage values in `detections.parquet`)

| edge type | links events sharing… | gate |
|---|---|---|
| `same_principal` | `principal_id` | within 30 min **and** same namespace (cloud events group on identity alone) |
| `same_session` | `session_name` | within 30 min — the **only** link from INC-C's IdP login to its AssumeRole |
| `external_session` | `external_session_id` | within 30 min |
| `shared_event` | `shared_event_id` | ungated (a UUID, unique per API call — AssumeRole→GetObject) |
| `same_resource` | `resource_id` **and** `principal_id` | within 2 h — bridges INC-A's RunInstances→TerminateInstances (91-min gap, one instance) |

Windows are tunable in [graph/entities.py](graph/entities.py) (`TIME_WINDOW_S`,
`RESOURCE_WINDOW_S`).

### Seed-originated 1-hop expansion (enforced at build time)

Seeds are `predicted_risky` events. Within each edge key we keep only clusters containing ≥1 seed
and star-connect their members from a seed; clusters with no seed are dropped. So an unflagged
**bridge** event (e.g. the benign IdP login linking a compromised session) enters the graph only
when a seed reaches it, and it never pulls in *its* other neighbours. The invariant **every edge
has ≥1 seed endpoint** holds, which is exactly seed→bridge (1 hop) and seed→bridge←seed (the
cross-source case), while forbidding seed→bridge→bridge. Connected components alone cannot make
this distinction — hence it is enforced in [graph/build_graph.py](graph/build_graph.py), not at
component time. A side benefit: bridge expansion *recovers* risky events the detector missed by
linking them to flagged seeds (recall 84% → 100% on the canonical dataset).

## Incident schema (`incidents.parquet`)

`incident_id` · `member_record_ids` (list) · `event_count` · `n_flagged` · `n_bridge` ·
`principal_ids` / `namespaces` / `resource_ids` (lists) ·
`source_cloudtrail_count` / `source_k8s_count` / `source_idp_count` (flat ints) ·
`edge_types` (the chain signature) · `start_time` / `end_time` / `window_s` ·
`severity_floor` (HIGH if any member HIGH) · `max_ensemble_score` · `tripwire_hits`.
Incidents are numbered `INC-0001…` by (start_time, smallest record_id) — deterministic across runs.
Ground-truth columns (`campaign_id`, `true_incident_id`) are joined only in `evaluate.py`.

## Verified

`build` → 4,288 flagged events collapse to **529 incidents**. `evaluate`:

- **Alert reduction 89%** (4,638 raw flags → 529 incidents; same denominator as Stage 2).
  Target ≥40%.
- **Correlation accuracy** vs `campaign_id`: homogeneity 0.88, completeness 0.99, V-measure 0.93.
- **Canonical recovery:** INC-A (40 → 1), INC-B (exposed pod → 1), INC-C (cross-source chain → 1,
  spans CloudTrail + IdP). INC-D's two labelled events split into two incidents by design (they
  share no surfaced linkage key); the credential-abuse `rbac_change` still surfaces as its own
  HIGH incident, and the autoscaler noise around it collapses.

Precision is intentionally *not* the headline here — event-level precision drops as benign bridge
neighbours join incidents; incident-level risk ranking is the **risk_fusion** stage's job. 8/8
tests green.
