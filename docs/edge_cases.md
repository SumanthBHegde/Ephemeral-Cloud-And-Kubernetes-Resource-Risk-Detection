# Edge Cases — Ephemeral Cloud & Kubernetes Resource Risk Detection

This document describes the edge cases that the risk detection system must identify and handle.  
Cases are grouped into **Observed** (present in `events_enriched.parquet`) and **Required** (gaps the system must still cover).

---

## Part 1 — Observed Edge Cases (from data)

These are behavioural patterns already present in the enriched event dataset that the detection pipeline must correctly score and flag.

---

### EC-01 · Novel / Unknown Principal

**Category:** Identity Anomaly  
**Count in data:** 3,049 events (30.9%)  
**Fields:** `is_novel_principal = True`, `principal_novelty > 0`

**Description:**  
A principal (user, service account, or role) that has never been seen before — or has appeared only very recently — performs an action on a cloud or Kubernetes resource. The system has no historical baseline for this actor.  

**Why it matters:**  
Novel principals are a primary indicator of compromised credentials, newly provisioned rogue accounts, or lateral movement by an attacker using a freshly created identity. Even a legitimate new principal acting on sensitive resources at odd times is high risk.

**Detection signal:**  
`principal_novelty` score + `cohort_deviation` spike on first-seen events. Flag when `is_novel_principal = True` AND the action touches a write or admin operation.

---

### EC-02 · Off-Hours Activity

**Category:** Temporal Anomaly  
**Count in data:** 1,609 events (16.3%)  
**Fields:** `off_hours_flag = 1`

**Description:**  
Events that occur outside the organisation's defined business hours window. Covers all three sources — IDP logins, AWS API calls, and Kubernetes pod operations.

**Why it matters:**  
Legitimate users and CI pipelines operate on predictable schedules. Activity outside those windows — especially for human actors — is a strong signal of unauthorised access, credential theft, or automated exfiltration running under cover of low visibility.

**Detection signal:**  
`off_hours_flag = 1`. Severity increases when combined with write actions (`read_only = False`), novel principals (EC-01), or sensitive resource types (`AWS::S3::Bucket`, `clusterrolebinding`).

---

### EC-03 · Service Account Burst / API Spray

**Category:** Behavioural Anomaly  
**Count in data:** 261 events with burst rate > 29 (100% from `ServiceAccount`)  
**Fields:** `burst_rate`, `principal_type = ServiceAccount`

**Description:**  
A service account fires an unusually high number of API calls within a short time window — far exceeding the normal rate for its cohort. In the data, burst outliers (>3 standard deviations above mean) are exclusively service accounts, peaking at 56 events/window.

**Why it matters:**  
Burst behaviour from service accounts indicates runaway automation, a compromised CI token being used for enumeration, or a denial-of-service attempt against a Kubernetes API server or AWS control plane.

**Detection signal:**  
`burst_rate > cohort_mean + 3σ`. Cross-check against known CI/CD pipeline schedules. Alert when bursting SA touches non-read-only paths.

---

### EC-04 · Publicly Exposed Resource

**Category:** Exposure Risk  
**Count in data:** 667 events (6.8%)  
**Fields:** `public_exposure_flag = 1`, `resource_type` in `[AWS::EC2::Instance, service, pod]`

**Description:**  
A resource — EC2 instance, Kubernetes service, or pod — is accessible from the public internet at the time of the event. The exposure may be intentional (load balancer) or accidental (misconfigured security group / `NodePort` service).

**Why it matters:**  
Public exposure drastically increases the attack surface. Any write action, privilege escalation, or configuration change on a publicly exposed resource carries a multiplied risk compared to internal-only resources.

**Detection signal:**  
`public_exposure_flag = 1`. Escalate immediately when combined with `read_only = False` (all 667 exposed events are also write events in this dataset), or when the resource is in `prod` namespace / `us-east-1`.

---

### EC-05 · Privileged Pod Execution (Kubernetes)

**Category:** Container Security  
**Count in data:** 129 events (all in `dev` namespace)  
**Fields:** `privileged = True`, `resource_type = pod`

**Description:**  
A Kubernetes pod is created or already running with `privileged: true` in its security context. A privileged container has near-full access to the host kernel and all devices — essentially equivalent to root on the node.

**Why it matters:**  
A privileged pod is one of the most critical misconfigurations in Kubernetes. An attacker or compromised workload running inside a privileged pod can escape to the host node, access node credentials, or pivot to other cluster resources.

**Detection signal:**  
`privileged = True` on `pod_create` action. Even in `dev`, this should generate a medium-severity alert. In `prod` or `kube-system`, it must be critical.

---

### EC-06 · Host Network Namespace Sharing (Kubernetes)

**Category:** Container Security  
**Count in data:** 129 events  
**Fields:** `host_network = True`

**Description:**  
A pod is created with `hostNetwork: true`, meaning it shares the node's network namespace instead of having an isolated pod network. The pod can see and bind to all ports on the host node.

**Why it matters:**  
A pod with host networking can sniff traffic from other pods on the node, bind to privileged ports, and potentially intercept node-level credentials or service mesh traffic. This is a common container escape vector.

**Detection signal:**  
`host_network = True` on `pod_create`. Treat as high risk when paired with `privileged = True` (EC-05), `broad_rbac = True`, or when the actor is a novel principal (EC-01).

---

### EC-07 · RBAC Rule Modification

**Category:** Privilege Escalation  
**Count in data:** 1 event  
**Fields:** `rbac_change = True`, `resource_type = clusterrolebinding`

**Description:**  
A Kubernetes RBAC rule — specifically a `ClusterRoleBinding` — is created or modified. This grants a subject (user, group, or service account) permissions across the entire cluster.

**Why it matters:**  
RBAC modifications are a critical escalation vector. An attacker who gains write access to the Kubernetes API can create a `ClusterRoleBinding` that grants `cluster-admin` to a compromised identity, achieving full cluster takeover. Even legitimate RBAC changes must be reviewed.

**Detection signal:**  
`rbac_change = True`. This should always generate a high-severity alert regardless of other context. The extremely low frequency (1 in ~10K events) makes it easy to surface.

---

### EC-08 · Overpermissive RBAC Grant

**Category:** Privilege Escalation  
**Count in data:** 1 event  
**Fields:** `broad_rbac = True`

**Description:**  
An RBAC binding grants overly broad permissions — for example, granting `get`, `list`, `watch` on `*` resources, or binding to a role with wildcard verbs. This is distinct from EC-07 in that the grant may be an existing rule, not necessarily a new modification.

**Why it matters:**  
Overly broad RBAC permissions violate the principle of least privilege. A service account with cluster-wide read access can enumerate all secrets, configmaps, and pod specs — providing an attacker with a complete map of the cluster.

**Detection signal:**  
`broad_rbac = True`. Flag for review. Correlate with `principal_novelty` to check if the over-permissive role was recently bound.

---

### EC-09 · Admin-Level Privilege Action

**Category:** Privilege Escalation  
**Count in data:** 130 events (1.3%)  
**Fields:** `privilege_level = 2`

**Description:**  
An action is performed with administrator-level privileges — for example, modifying an S3 bucket policy (`PutBucketPolicy`), creating or deleting cluster-wide RBAC bindings, or terminating EC2 instances. `privilege_level = 2` is the highest tier in the enrichment schema.

**Why it matters:**  
Admin-level actions can cause irreversible damage: data deletion, policy bypass, infrastructure destruction. They are the end goal of most attack chains and must be correlated against expected admin principals.

**Detection signal:**  
`privilege_level = 2`. Cross-reference against a whitelist of approved admin identities. Flag any admin action from a `FederatedUser`, `contractor`, or `is_novel_principal = True` actor.

---

### EC-10 · Proxy-Based Access

**Category:** Obfuscation / Evasion  
**Count in data:** 120 events (1.2%)  
**Fields:** `is_proxy = True`

**Description:**  
The request originates from an IP address identified as a proxy, VPN exit node, or anonymisation service. The actual geographic origin of the actor is obscured.

**Why it matters:**  
Legitimate enterprise users rarely route cloud API calls through proxies. Proxy usage is a common evasion technique used to obscure an attacker's real location, bypass IP-based allow-lists, or make cross-region activity appear local.

**Detection signal:**  
`is_proxy = True`. Elevate risk score. Combine with off-hours flag (EC-02) and novel principal (EC-01) for a high-confidence alert.

---

### EC-11 · Untagged / Unmanaged Resource

**Category:** Governance Gap  
**Count in data:** 5,926 events (60.1%)  
**Fields:** `tag_completeness = 0.0`

**Description:**  
The resource involved in the event has zero governance tags — none of `owner`, `environment`, `cost-center`, `managed-by`, `pipeline`, or `app` are populated. These resources cannot be attributed to a team, budget, or lifecycle policy.

**Why it matters:**  
Untagged resources are the canonical "ephemeral risk" this project targets. They are often orphaned, forgotten, or created outside of approved IaC pipelines. An attacker frequently creates resources without tags to avoid detection by cost/inventory monitoring tools.

**Detection signal:**  
`tag_completeness = 0`. Used as a base risk multiplier. When combined with public exposure (EC-04), elevated privilege (EC-09), or off-hours activity (EC-02), the composite score should be significantly elevated.

---

### EC-12 · High Cohort Deviation

**Category:** Behavioural Anomaly  
**Count in data:** 113 events (1.1%) with deviation > 5.14  
**Fields:** `cohort_deviation`, `cohort`

**Description:**  
The event's behavioural fingerprint (action type, time, resource, region) deviates significantly from the established baseline of the principal's peer cohort (e.g., `human_dev`, `ci_runner`). A high `cohort_deviation` score means this event is unlike anything the principal's peer group typically does.

**Why it matters:**  
Cohort deviation catches anomalies that novelty scores miss — for example, a known developer suddenly performing `PutBucketPolicy` (which their cohort never does) or a CI runner accessing `eu-west-1` when it always uses `us-east-1`.

**Detection signal:**  
`cohort_deviation > mean + 3σ` (~5.14 in this dataset). Top deviators: `human_dev` (81 events), `ci_runner` (32 events).

---

### EC-13 · Very Short Resource Exposure Window

**Category:** Ephemeral Resource Risk  
**Count in data:** 310 events with `exposure_window_s < 300`  
**Fields:** `exposure_window_s`, `is_spot`

**Description:**  
A resource exists for less than 5 minutes before being terminated or deleted. This covers spot instances, short-lived pods, and transient S3 objects. The resource lifecycle is so brief it may evade standard periodic inventory scans.

**Why it matters:**  
Attackers use extremely short-lived resources to exfiltrate data, run compute jobs, or establish beachheads that disappear before defenders notice. Spot instances and ephemeral pods are particularly attractive because they are designed to be transient and often lack logging.

**Detection signal:**  
`exposure_window_s < 300` (configurable threshold). Alert when combined with `public_exposure_flag = 1` or when the creating principal is novel (EC-01).

---

### EC-14 · Spot / Ephemeral Instance Activity

**Category:** Ephemeral Resource Risk  
**Count in data:** 346 events (3.5%)  
**Fields:** `is_spot = True`

**Description:**  
The event involves a spot instance — a type of EC2 instance that AWS can reclaim at any time and that is typically used for cost-optimised, interruptible workloads. Spot instances are inherently ephemeral and are often provisioned without full governance controls.

**Why it matters:**  
Spot instances are a common blind spot. They may not be included in standard patching cycles, may have relaxed security groups, and their transient nature means logs are frequently lost when the instance is reclaimed. Adversaries can run malicious workloads on spot instances knowing they will be automatically cleaned up.

**Detection signal:**  
`is_spot = True`. Baseline risk. Escalate when the instance has `public_exposure_flag = 1`, no tags (`tag_completeness = 0`), or is created off-hours.

---

### EC-15 · Cross-Region Activity

**Category:** Geographic Anomaly  
**Count in data:** 4,000 events (40.6%) across `us-east-1`, `us-west-2`, `eu-west-1`  
**Fields:** `region`

**Description:**  
An action is performed in a region that is either unexpected for the principal's cohort, or where the organisation has no declared workloads. Each principal should have a home region; deviations from it are suspicious.

**Why it matters:**  
Cross-region activity is used by attackers to bypass region-scoped SCPs (Service Control Policies), to store exfiltrated data in a region that isn't monitored, or to spin up resources in regions with weaker compliance controls. It also increases blast radius as resources may not be covered by regional backup or monitoring policies.

**Detection signal:**  
Compare `region` against the principal's historical region set. Flag first-time or rare region usage per cohort. Combine with off-hours (EC-02) or novel principal (EC-01) for high confidence.

---

## Part 2 — Required Edge Cases (gaps to implement)

These patterns are **not yet present or severely underrepresented** in the current dataset but are critical for a production-grade risk detection system.

---

### EC-16 · Cross-Source Attack Chain (IDP → CloudTrail → K8s)

**Category:** Multi-Hop Attack  
**Fields needed:** `shared_event_id`, `external_session_id`, cross-source join

**Description:**  
A single attack unfolds across all three event sources in sequence:  
1. An identity authenticates via Okta (IDP session event)  
2. The same identity assumes an AWS role via `AssumeRoleWithWebIdentity` (CloudTrail event)  
3. The assumed role then creates a privileged Kubernetes pod (K8s audit event)

Each individual event may appear low-risk in isolation, but the chained sequence is a textbook cloud privilege escalation path.

**Detection approach:**  
Link events using `shared_event_id` and `external_session_id`. Build a session graph within a sliding time window (~15 min). Score the chain holistically — if any hop crosses a risk threshold, elevate the entire chain's score.

---

### EC-17 · Role Chaining / Assume Role Cascade

**Category:** Privilege Escalation  
**Fields needed:** `action = AssumeRole`, `principal_arn`, chain tracking

**Description:**  
An identity assumes Role A, then uses Role A's credentials to assume Role B, then Role B to assume Role C — each step hopping to a more privileged role. AWS allows this by default and it is a common technique to "launder" permissions across trust boundaries.

**Detection approach:**  
Track `AssumeRole` events per session. Flag when the same `session_name` or `external_session_id` appears in more than 2 consecutive `AssumeRole` events within a short window. Compute the privilege delta between the starting and ending role.

---

### EC-18 · Data Exfiltration Pattern (Bulk Object Read)

**Category:** Exfiltration  
**Fields needed:** `action = GetObject`, `resource_id`, volume counting per principal/session

**Description:**  
A principal reads an unusually large number of S3 objects (`GetObject`) within a single session — far beyond what their cohort normally accesses. This is the primary cloud data exfiltration pattern.

**Detection approach:**  
Count `GetObject` events per `principal_id` per session window. Compute against cohort baseline. Flag when volume exceeds `cohort_mean + 3σ`. Also flag when the accessed bucket is tagged with sensitive labels or belongs to a production environment.

---

### EC-19 · Privilege Escalation Within a Session

**Category:** Privilege Escalation  
**Fields needed:** `privilege_level`, `session_name` / `external_session_id`, time ordering

**Description:**  
Within a single authenticated session, the actor begins with low-privilege actions (reads, describes) and progressively moves to higher-privilege write or admin actions. This "low-and-slow" privilege ramp is a hallmark of insider threat and living-off-the-land attacks.

**Detection approach:**  
Track `privilege_level` progression over time within the same session. Alert when a session starts at `privilege_level = 0` and reaches `privilege_level ≥ 1` within the same window, especially when the step-up involves a new `AssumeRole`.

---

### EC-20 · Kubernetes Namespace Escape Attempt

**Category:** Container Security  
**Fields needed:** `namespace`, `resource_type`, `action`, `privileged`, `host_network`

**Description:**  
A workload in a restricted namespace (e.g., `dev`, `ci`) attempts to access or create resources in a privileged namespace (e.g., `kube-system`, `prod`). Namespace boundaries are a fundamental Kubernetes isolation primitive — crossing them without authorisation is a serious security event.

**Detection approach:**  
Track sequences where the same principal acts in a low-trust namespace and then in `kube-system` within a short window. Also flag `pod_create` events in `kube-system` from non-system service accounts, or any `clusterrolebinding` creation from a `dev`/`ci` namespace actor.

---

### EC-21 · Service Account Token Misuse

**Category:** Identity Abuse  
**Fields needed:** `principal_type = ServiceAccount`, `source_ip`, `source`, cohort comparison

**Description:**  
A Kubernetes service account token is used to make API calls from an unexpected source — for example, from a CloudTrail event (SA token used to call AWS APIs directly) or from an IP outside the cluster's CIDR range. This indicates the token has been exfiltrated and is being used by an external actor.

**Detection approach:**  
For `ServiceAccount` principals, validate that `source_ip` falls within expected cluster node CIDRs. Flag any `ServiceAccount` principal appearing in `cloudtrail` source events (SA tokens should never be used to call AWS APIs directly). Cross-reference with `is_novel_principal`.

---

### EC-22 · Sensitive Namespace Action (kube-system)

**Category:** Container Security  
**Fields needed:** `namespace = kube-system`, `action`, `principal_type`

**Description:**  
Any create, delete, or modify action targeting resources in the `kube-system` namespace. This namespace hosts critical cluster components (CoreDNS, kube-proxy, metrics-server) and modifications to it can destabilise the entire cluster or create persistent backdoors.

**Detection approach:**  
Any `pod_create`, `pod_delete`, or `rbac_change` in `namespace = kube-system` from a non-system service account should trigger a critical alert. Treat this namespace as a zero-tolerance zone for non-approved actors.

---

### EC-23 · Contractor / Third-Party Principal Access

**Category:** Third-Party Risk  
**Fields needed:** `cohort`, `principal_id` pattern matching for contractors

**Description:**  
A contractor or external partner identity accesses internal resources. Contractors should operate with tightly scoped, time-limited permissions. Any contractor access outside their approved scope, outside business hours, or involving sensitive resources is high risk.

**Detection approach:**  
Identify contractor principals by `principal_id` pattern (e.g., `contractor-*@partner.example`) and `role_name = data-access-role`. Build a contractor-specific cohort baseline. Flag access to resources beyond the approved scope, admin actions (`privilege_level ≥ 1`), and any off-hours access.

---

### EC-24 · Long-Lived or Expired Session Reuse

**Category:** Session Anomaly  
**Fields needed:** `session_ttl`, `external_session_id`, event time delta

**Description:**  
A session that has exceeded its declared TTL (`session_ttl` seconds) continues to generate events — indicating either a clock skew issue, a token refresh vulnerability, or a stolen long-lived token being replayed. Also covers sessions with `session_ttl` set to the maximum (3600s) which may indicate a deliberately extended session.

**Detection approach:**  
Compare `event_time` against session start time + `session_ttl`. Flag events that arrive after expiry. Additionally, flag sessions where `session_ttl = 3600` (maximum) for human actors, since legitimate interactive sessions should have shorter lifetimes.

---

### EC-25 · Bucket Policy Modification on Public or Production Bucket

**Category:** Data Protection  
**Fields needed:** `action = PutBucketPolicy`, `resource_type = AWS::S3::Bucket`, `tags`

**Description:**  
A bucket policy is modified (`PutBucketPolicy`) on a bucket that is either publicly accessible or tagged as a production resource. Bucket policy changes can silently open previously private data to the internet or to cross-account access.

**Detection approach:**  
Any `PutBucketPolicy` event is medium risk by default. Elevate to critical when `public_exposure_flag = 1` or when the bucket's `environment` tag is `prod`. Cross-reference the new policy against a known-safe policy template and diff for new `Allow` statements with `Principal: "*"`.

---

## Edge Case Coverage Matrix

| ID | Name | In Data | Severity | Priority |
|---|---|---|---|---|
| EC-01 | Novel Principal | ✅ Yes | High | P1 |
| EC-02 | Off-Hours Activity | ✅ Yes | Medium | P1 |
| EC-03 | Service Account Burst | ✅ Yes | High | P1 |
| EC-04 | Publicly Exposed Resource | ✅ Yes | Critical | P1 |
| EC-05 | Privileged Pod | ✅ Yes | Critical | P1 |
| EC-06 | Host Network Sharing | ✅ Yes | High | P1 |
| EC-07 | RBAC Modification | ✅ Yes (1 event) | Critical | P1 |
| EC-08 | Overpermissive RBAC | ✅ Yes (1 event) | High | P1 |
| EC-09 | Admin-Level Privilege | ✅ Yes | Critical | P1 |
| EC-10 | Proxy-Based Access | ✅ Yes | Medium | P2 |
| EC-11 | Untagged Resource | ✅ Yes | Low–Medium | P2 |
| EC-12 | High Cohort Deviation | ✅ Yes | High | P1 |
| EC-13 | Short Exposure Window | ✅ Yes | Medium | P2 |
| EC-14 | Spot Instance Activity | ✅ Yes | Low | P3 |
| EC-15 | Cross-Region Activity | ✅ Yes | Medium | P2 |
| EC-16 | Cross-Source Attack Chain | ❌ Gap | Critical | P1 |
| EC-17 | Role Chaining | ❌ Gap | Critical | P1 |
| EC-18 | Bulk Data Exfiltration | ❌ Gap | Critical | P1 |
| EC-19 | Privilege Escalation in Session | ❌ Gap | High | P1 |
| EC-20 | Namespace Escape Attempt | ❌ Gap | Critical | P1 |
| EC-21 | Service Account Token Misuse | ❌ Gap | Critical | P1 |
| EC-22 | Sensitive Namespace (kube-system) | ❌ Gap | Critical | P1 |
| EC-23 | Contractor Access | ❌ Gap | High | P2 |
| EC-24 | Long-Lived Session Reuse | ❌ Gap | High | P2 |
| EC-25 | Bucket Policy Modification | ❌ Gap | Critical | P1 |

---

## Compound / Combo Cases

The following combinations produce the highest-confidence risk signals and should trigger immediate escalation:

| Combination | Cases | Confidence |
|---|---|---|
| Off-hours + Novel principal + Write action | EC-01 + EC-02 | Very High |
| Privileged pod + Host network + Novel SA | EC-05 + EC-06 + EC-01 | Critical |
| Public exposure + Write action + Untagged | EC-04 + EC-11 | Very High |
| High burst + Off-hours + Service account | EC-03 + EC-02 | High |
| Admin privilege + Proxy access + Off-hours | EC-09 + EC-10 + EC-02 | Critical |
| Cross-source chain + Namespace escalation | EC-16 + EC-20 | Critical |
| Role chaining + Bulk S3 reads | EC-17 + EC-18 | Critical |
