# Ephemeral Cloud & Kubernetes Resource Risk Detection

**Track:** Cloud Security Governance & Risk
**Difficulty:** Intermediate–Advanced

**Enterprise Challenge:** Ephemeral cloud resources exist for minutes—but attackers need even less time. Are your governance and detection controls fast enough to manage transient risk?

---

## The Business Problem

**Scenario:** A cloud-native enterprise runs 500+ Kubernetes workloads and provisions hundreds of ephemeral cloud resources daily — CI/CD job pods, spot instances, temporary IAM sessions, and autoscaled containers. These assets exist for minutes to hours, then disappear. Traditional security controls (quarterly scans, daily inventory syncs) were never designed for this tempo.

### Real Incidents

- **Case 1:** Attacker compromised a CI/CD service account, spun up 20 spot VMs for crypto mining at 3 AM — all terminated before the morning SOC shift. Total cost: $14,000 in 90 minutes; zero alerts fired.
- **Case 2:** Developer created a debug pod with a NodePort exposed to 0.0.0.0/0 for "quick testing." Pod ran for 11 minutes — long enough for an external scanner to find and exploit it.
- **Case 3:** Short-lived assumed-role session accessed production S3 buckets containing PII. Session expired in 15 minutes; no correlation to the compromised Lambda function that triggered it.
- **Case 4:** Autoscaler burst created 40 pods in 2 minutes during a legitimate traffic spike — SOC received 40 individual alerts, all false positives, burying a real credential-abuse alert.

### The Pain

- Traditional asset inventory runs too slowly for minute-long resources
- High alert volumes from autoscaling and CI/CD create analyst fatigue
- Identity/session context is fragmented across cloud, K8s, and IAM logs
- Teams investigate isolated alerts but miss campaign-level behavior
- Post-incident forensics are impossible when the resource no longer exists

### Real Impact

- Short-lived exposed assets can be compromised before scheduled scans run
- SOC teams waste effort on noisy one-off alerts with little correlation
- Compliance teams cannot prove continuous monitoring for ephemeral workloads
- Financial exposure from resource hijacking (crypto mining on your bill)

### Compliance Impact

- **NIST CM-8:** Asset inventory must include transient/ephemeral resources
- **NIST SI-4:** Continuous monitoring must cover dynamic workloads
- **CIS Kubernetes Benchmark:** Pod security, RBAC, and network policies
- **GDPR Article 32:** Security of processing — ephemeral workloads handling PII must be governed

---

## Challenge Overview

Build a system to:

1. Discover ephemeral cloud/Kubernetes assets and identities in near real time
2. Classify resources as ephemeral vs persistent using heuristics and AI
3. Detect risky transient behavior (exposure, abuse, unusual API patterns)
4. Correlate related events into incidents to reduce alert noise
5. Assign risk scores at resource and incident levels
6. Generate analyst-ready narratives with evidence, likely intent, and remediation

---

## Data Reality & Edge Cases

Ephemeral environments introduce the following real-world challenges:

### Classification Ambiguity

- Assets that exist for only minutes vs long-running pods with short TTL labels
- CI/CD job pods vs attacker-created pods (both are short-lived)
- Autoscaler bursts vs malicious resource creation bursts (identical API patterns)
- Spot instances reclaimed by cloud provider vs instances terminated by attacker covering tracks

### Identity & Session Complexity

- Assumed-role sessions with 15-minute TTL — legitimate automation or stolen token?
- Service account tokens shared across pods in same namespace
- Federated identities with ephemeral credentials from external IdPs
- CI/CD service accounts with broad permissions (legitimate but high blast radius)

### Detection Challenges

- Resource gone before alert is triaged (no forensic evidence remains)
- High-frequency legitimate bursts mask malicious bursts
- Public IP assignment is normal for load balancers but risky for debug pods
- Crypto mining uses the same CPU patterns as legitimate batch compute
- Historical baselines are hard to establish for ephemeral workloads (no stable identity)

### Ambiguous Scenarios Your System Must Handle

- 40 pods created in 2 minutes — HPA autoscale responding to traffic or resource hijacking?
- Spot VM with public IP and no tags — misconfigured CI job or attacker staging?
- Assumed-role session accesses S3 at 3 AM — scheduled Lambda or compromised credential?
- Debug pod with privileged security context runs for 5 minutes — developer troubleshooting or container escape?

---

## Approach Options

### Option A: ML-Driven Detection + LLM Triage (Advanced)

**Best for:** Cloud security engineers, ML teams

**Technical Approach:**
- Simulate realistic cloud audit + K8s event streams (JSON/CSV with timestamps, principals, tags, resource metadata)
- Extract features per event window: burst rate, principal novelty, tag completeness, privilege level, public exposure flag, TTL
- Train anomaly detection model (Isolation Forest or autoencoder) on normal CI/CD and autoscale patterns
- Score each event; cluster related high-score events into incidents using time-window + identity + namespace correlation (NetworkX graph)
- Use LLM API to generate per-incident analyst narratives: evidence summary, likely intent, MITRE mapping, and recommended guardrails
- Build interactive dashboard: ephemeral inventory, TTL distribution, burst timeline, incident list with drill-down

**Stack:** Python, scikit-learn, NetworkX, LLM API (OpenAI/HuggingFace), Pandas, Plotly

**Complexity:** 4/5
**Effort:** 35–45 hours (includes ~8–10 hours for data simulation)

---

### Option B: Heuristic + Statistical Correlation Engine (Intermediate)

**Best for:** Security analysts, backend engineers

**Technical Approach:**
- Generate simulated event data with labeled ground truth (scripts provided or self-built)
- Classify resources as ephemeral using TTL thresholds, label presence, controller ownership, and known autoscaling patterns
- Define risk signals: public IP on non-LB resource, privileged pod without controller, burst count exceeding rolling baseline, off-hours assumed-role activity
- Score each signal using Z-score/IQR against per-namespace or per-principal baselines
- Correlate co-occurring signals by identity + namespace + 5-minute time window into clustered incidents
- Output prioritized incident queue with evidence snippets and severity ranking
- Visualize: burst timeline, TTL histogram, top-risk resources/identities

**Stack:** Python, Pandas, NumPy/SciPy, SQLite, Plotly

**Complexity:** 3/5
**Effort:** 25–35 hours (includes ~5–8 hours for data simulation)

---

### Option C: Rule-Based Ephemeral Risk Monitor (Beginner-Intermediate)

**Best for:** SOC automation beginners, GRC analysts

**Technical Approach:**
- Create a small simulated dataset (200–500 events in CSV/JSON with manual labels)
- Define detection rules in JSON format:
  - "Public IP on ephemeral compute" → HIGH
  - "Privileged pod without controller owner" → HIGH
  - "Burst create >10 resources in 5 min" → MEDIUM
  - "Assumed-role session outside business hours" → MEDIUM
- Build rule engine to evaluate each event and assign risk score: (rule severity × exposure window × privilege level)
- Simple web dashboard showing:
  - Risky ephemeral resources (sorted by score)
  - Burst timeline chart (events per minute)
  - Resource TTL distribution
  - Alert list with rule match explanation
- Export flagged events to CSV for SOC review

**Stack:** Python (Flask/FastAPI), CSV/JSON ingestion, HTML/CSS/JS (Plotly or Chart.js)

**Complexity:** 2/5
**Effort:** 15–25 hours (includes ~3–5 hours for data creation)

---

## Sample Data Provided

This problem statement does not provide a pre-built sample dataset. Participants must generate or simulate their own telemetry. Your simulated data should include at minimum:

| Source | Records (suggested) | Description |
|---|---|---|
| Cloud audit logs | 500–1,000 | API calls: RunInstances, AssumeRole, CreateBucket, etc. with timestamps, principals, tags |
| Kubernetes events | 500–1,000 | Pod create/delete, service exposure, RBAC changes with namespace, labels, controller owner |
| Identity/session logs | 200–500 | Assumed-role sessions, service account token issuance, federation events |

### Expected Anomaly Mix in Simulated Data

- Resource hijacking (crypto mining bursts): ~5–8% of events
- Public exposure of ephemeral compute: ~3–5%
- Unexpected identity/session activity: ~5–8%
- Legitimate autoscaling / CI/CD bursts: ~40–50% (noise your system must suppress)
- Routine ephemeral lifecycle (normal): ~30–40%

---

## Self-Evaluation

### Success Criteria

| Metric | Target | Why |
|---|---|---|
| Ephemeral Asset Visibility | 95%+ identified | Ensure short-lived resources are not missed |
| Detection Latency | Near real-time | Catch risk before assets disappear |
| Noise Reduction | ≥40% alert reduction | Prevent SOC alert fatigue |
| Incident Correlation Accuracy | High-confidence clustered incidents | Surface campaigns, not isolated events |
| Risk Scoring Quality | Aligns with analyst judgment | Prioritize truly risky ephemeral activity |
| Analyst Readiness | Single-incident narratives | Enable faster investigation and response |

### Self-Evaluation Code Snippet

```python
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

# Assuming you create ground truth labels for your simulated data
labels = pd.read_csv('ephemeral_event_labels.csv')
# labels['predicted_risky'] = your_detector.predict(events)

y_true = labels['is_risky'].astype(int)
y_pred = labels['predicted_risky'].astype(int)

print(f"Precision: {precision_score(y_true, y_pred):.2%}")
print(f"Recall:    {recall_score(y_true, y_pred):.2%}")
print(f"F1 Score:  {f1_score(y_true, y_pred):.2f}")

# Noise reduction: how many raw alerts did clustering reduce?
raw_alerts = len(labels[labels['predicted_risky'] == True])
clustered_incidents = labels[labels['predicted_risky'] == True]['incident_id'].nunique()
print(f"Alert reduction: {raw_alerts} alerts → {clustered_incidents} incidents ({(1 - clustered_incidents/raw_alerts)*100:.0f}% reduction)")
# Target: Precision > 75%, Recall > 70%, Alert reduction ≥ 40%
```

---

## Deliverables

- Working prototype using real or simulated logs (with a short data dictionary)
- Ephemeral classifier + detection rules/ML approach explained clearly
- Dashboard showing ephemeral inventory/TTL distribution, creation spikes, top risky resources/identities, and an incident list with narratives
- Architecture diagram (ingest → enrich → detect → cluster → score → LLM narrative → dashboard)
- Documentation with 2–3 sample incidents: evidence, MITRE mapping, and recommended guardrails

---

## Framework Alignment

### NIST SP 800-53

- **CM-8:** Information System Component Inventory (ephemeral assets must be tracked)
- **SI-4:** Information System Monitoring (continuous detection)
- **IR-4:** Incident Handling (correlated incident response)

### MITRE ATT&CK

- **T1578:** Modify Cloud Compute Infrastructure
- **T1496:** Resource Hijacking (crypto mining)
- **T1190:** Exploit Public-Facing Application

### CIS Benchmarks

- Kubernetes CIS Benchmark (pod security, RBAC)
- Cloud provider CIS Benchmarks (security groups, IAM)