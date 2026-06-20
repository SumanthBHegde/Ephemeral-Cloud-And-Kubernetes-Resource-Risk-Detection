# `events_enriched.parquet` — Data Explanation

## Overview

| Property | Value |
|---|---|
| **Rows** | 9,857 events |
| **Columns** | 43 fields |
| **Time Range** | ~June 2026 (recent data) |
| **Purpose** | Enriched, cross-source security event log for ephemeral cloud & Kubernetes risk detection |

---

## Event Sources (`source` column — 3 values)

| Source | Description |
|---|---|
| `idp_session` | Okta / Identity Provider login and SSO events |
| `cloudtrail` | AWS CloudTrail API calls (S3, EC2, IAM, STS) |
| `k8s_audit` | Kubernetes API server audit logs (pod create/delete, RBAC changes) |

This multi-source design is the core of the project — correlating identity, cloud, and Kubernetes events for a holistic risk view.

---

## Column Groups

### 🆔 Identity & Identity Columns (always present)

| Column | Type | Notes |
|---|---|---|
| `record_id` | UUID string | Unique event ID — 9,857 unique values, no nulls |
| `event_time` | `datetime64[UTC]` | Timestamp of event (timezone-aware) |
| `source` | string | `idp_session` / `cloudtrail` / `k8s_audit` |
| `action` | string | 16 unique actions (e.g. `user.authentication.sso`, `AssumeRole`, `pod_create`) |
| `principal_id` | string | 3,049 unique actors (emails, service accounts, AWS role IDs) |
| `principal_type` | string | 6 types: `User`, `AWSService`, `AssumedRole`, `FederatedUser`, `ServiceAccount`, `IAMUser` |
| `outcome` | string | `SUCCESS` / `FAILURE` |

### 🔐 AWS / IAM Columns (sparse — mostly CloudTrail only)

| Column | Nulls | Notes |
|---|---|---|
| `principal_arn` | 6,737 | Full AWS ARN of the actor |
| `role_name` | 7,513 | 3 roles: `scheduled-lambda-role`, `data-access-role`, `ci-runner-role` |
| `assumed_role_id` | 9,231 | `AROA...` role assumption ID |
| `region` | 5,857 | 3 regions: `us-east-1`, `us-west-2`, `eu-west-1` |
| `session_name` | 7,731 | Role session name (e.g. `etl-nightly`, `contractor-jnu5`) |
| `session_ttl` | 9,231 | Session lifetime in seconds (900–3600s range) |
| `shared_event_id` | 8,830 | Links IDP session to a CloudTrail assume-role event |

### ☸️ Kubernetes Columns (sparse — K8s audit only)

| Column | Nulls | Notes |
|---|---|---|
| `namespace` | 5,500 | 6 namespaces: `prod`, `dev`, `build`, `web`, `ci`, `kube-system` |
| `controller_owner` | 7,169 | Owning controller of the resource |
| `privileged` | 0 | Bool — pod runs with privileged security context |
| `host_network` | 0 | Bool — pod shares host network namespace |
| `rbac_change` | 0 | Bool — event modified RBAC rules |
| `broad_rbac` | 0 | Bool — RBAC grants overly broad permissions |
| `service_type` | 9,665 | K8s service type (e.g. LoadBalancer) |
| `exposed_open` | 0 | Bool — resource is publicly exposed |

### 🌐 Network / Session Columns

| Column | Nulls | Notes |
|---|---|---|
| `source_ip` | 0 | 2,050 unique IPs (mix of internal `10.x` and public) |
| `public_ip` | 9,511 | Public IP if resource has one |
| `is_proxy` | 8,357 | Bool — request came through a proxy |
| `external_session_id` | 8,357 | IDP session ID |

### 🏷️ Resource Columns

| Column | Nulls | Notes |
|---|---|---|
| `resource_id` | 2,348 | 4,975 unique resources (S3 objects, pod names, ARNs) |
| `resource_type` | 848 | 7 types: `session`, `AWS::S3::Object`, `AWS::S3::Bucket`, `pod`, `AWS::EC2::Instance`, `service`, `clusterrolebinding` |
| `is_spot` | 0 | Bool — resource is a spot instance/ephemeral node |
| `tags` | 0 | Dict of AWS resource tags (`owner`, `environment`, `cost-center`, `managed-by`, `pipeline`, `app`) |
| `labels` | 0 | Dict of K8s labels |
| `read_only` | 0 | Bool — was the action read-only? |

### 📊 Engineered / Risk Feature Columns

These are the **computed enrichment fields** that feed ML models or rule-based scoring:

| Column | Type | Description |
|---|---|---|
| `cohort` | string | Principal cohort group (e.g. `human_dev`, `contractor`, `ci-bot`) |
| `burst_rate` | int | # events from this principal in the burst window (1–56, mean ~6) |
| `principal_novelty` | int | How new/unfamiliar this principal is (0 = known, up to 2344) |
| `is_novel_principal` | bool | Binary flag derived from `principal_novelty` |
| `tag_completeness` | float | Fraction of expected tags that are populated (0.0–1.0) |
| `privilege_level` | int | Computed privilege score (0=none, 1=elevated, 2=admin) |
| `public_exposure_flag` | float | 0 or 1 — resource is publicly accessible |
| `exposure_window_s` | float | Duration (seconds) the resource was exposed (104–3600s) |
| `off_hours_flag` | int | 1 if event occurred outside business hours |
| `cohort_deviation` | float | How much this event deviates from the principal's cohort baseline (higher = more anomalous) |

### 📦 Raw Event Column

| Column | Notes |
|---|---|
| `raw` | Full original JSON payload (Okta event, CloudTrail record, or K8s audit entry) — useful for forensics |

---

## Key Observations

### 1. Sparse by Design
Most AWS/K8s-specific fields have many nulls because they only apply to one source. For example, `namespace` is null for all CloudTrail/IDP events — this is expected and structurally correct.

### 2. Risk Signal Distribution
| Feature | Notable Stats |
|---|---|
| `burst_rate` | Mean 6, max 56 — outliers indicate burst/spray activity |
| `off_hours_flag` | 16.3% of events are off-hours |
| `public_exposure_flag` | 4.7% of events involve publicly exposed resources |
| `privilege_level` > 0 | ~6% events involve elevated/admin privileges |
| `cohort_deviation` | Mean 1.55, max 12.75 — high deviation = anomaly candidate |

### 3. Linked Session Chain
`shared_event_id` + `external_session_id` allow cross-source session linking: an Okta SSO login → AWS AssumeRole via WebIdentity → S3/EC2 action can be traced as a single chain.

### 4. Tag Completeness as a Risk Signal
`tag_completeness = 0` for 75%+ of events means most resources lack proper governance tags — this is itself a risk indicator for ephemeral/unmanaged resources.

### 5. Novel Principals
`is_novel_principal` is `True` for many events even with `principal_novelty = 0` — likely a logic inversion that's worth verifying in the enrichment pipeline.

---

## Data Flow Position

```
Raw Sources
  ├── Okta Logs        ─┐
  ├── AWS CloudTrail   ─┼──► [Normalization] ──► [Enrichment] ──► events_enriched.parquet
  └── K8s Audit Logs  ─┘                          (this file)
                                                        │
                                               [Risk Scoring / ML]
                                               [Alerting / Dashboard]
```
