
## Cloud audit logs

| Source | What it actually is | Caveat |
|---|---|---|
| **flaws.cloud public CloudTrail dataset (Summit Route / Scott Piper)** | Anonymized real CloudTrail logs covering over 3.5 years of genuine attacker activity against a deliberately vulnerable AWS training environment — largely attacks, not staged simulations, released as a downloadable tarball. This is the best single find here: real attacker CloudTrail behavior, already captured, no AWS account needed. | It's old-ish (2017–2020 era attacks) and AWS event schemas have evolved since, so use it for attacker *behavior patterns* and field structure, not as a literal drop-in replacement for your generator |
| **Stratus Red Team (Datadog)** | An open-source adversary emulation tool covering AWS, Azure, GCP, and Kubernetes, with each technique mapped to MITRE ATT&CK — running it against a real sandbox account produces real CloudTrail entries for ~20+ specific attack techniques | This is a tool, not a dataset — you'd need a real (even free-tier) AWS account to generate output, same cost/setup tradeoff we discussed earlier |
| **Mordor / Security-Datasets project (OTRF)** | Pre-recorded security events from simulated adversarial techniques, released as JSON, categorized by platform and mapped to MITRE ATT&CK tactics and techniques, including the benign events happening around the attack | Skews Windows/AD-heavy historically; check before assuming AWS-specific coverage is deep |
| AWS's own CloudTrail documentation | Official sample JSON for every event type (RunInstances, AssumeRole, etc.) — not a dataset, but the authoritative field-level schema reference | Use this to verify your generator's field names match real CloudTrail exactly |

## Kubernetes events

| Source | What it actually is | Caveat |
|---|---|---|
| **Official Kubernetes audit log schema docs** | Documents the audit.k8s.io request/response record format — source IP, requesting user, impersonation info, resource being requested | Reference schema, not event volume — but this is the field list you want to match exactly |
| **liggitt/audit2rbac sample audit log (GitHub)** | A small sample audit log containing real-shaped requests from users "alice," "bob," and a service account, in valid audit.k8s.io JSON | Tiny — useful for confirming your JSON structure is realistic, not for volume |
| **Stratus Red Team's Kubernetes module** | Same tool as above, also covers K8s-specific attack techniques (privilege escalation, exposure) | Same real-cluster requirement caveat |

## Workload timing realism (burst size/speed patterns — not security-labeled, but useful)

| Source | What it actually is | Caveat |
|---|---|---|
| **Google Cluster Trace (Borg)** | Real workload traces from Google's Borg-managed compute cells — multiple releases, including a 29-day single-cell trace and an 8-cell trace from May 2019, recording every job submission and task event | No security labels at all — pure value here is grounding realistic *timing distributions* for how real autoscale/burst events actually arrive, which directly feeds the "legit burst must look like the malicious burst" design principle |
| **Alibaba Cluster Trace** | A production cluster trace covering about 1,300 machines over a 12-hour period, including container and batch-job event files, with later GPU-focused releases | Same use case as Google's trace — timing realism, not anomaly ground truth |

## Identity/session logs

There's no dedicated public dataset specifically for ephemeral assumed-role/session abuse the way CERT covered insider-threat identity behavior — this is the weakest-covered of your three sources. Your best real-world grounding here is actually a side effect of the cloud-audit sources above: flaws.cloud and Stratus Red Team both touch credential-access and AssumeRole-related techniques, so the session-level behavior you'd want to mimic (TTL patterns, off-hours sessions, scope mismatches) is implicitly present in CloudTrail-side `AssumeRole` records rather than a separate identity-specific feed.

## Practical recommendation

Same approach as before: don't try to ingest any of these wholesale — your generator needs the labeled ground truth (`true_incident_id`, `severity`) that none of these provide, since they're either unlabeled (Google/Alibaba) or labeled for a different purpose (Mordor's MITRE mapping isn't your incident-correlation ground truth). The actual payoff is **field-level and behavioral grounding**: pull a few real flaws.cloud CloudTrail records to verify your `cloud_audit_logs` schema matches real AWS exactly, and skim Google's cluster trace to sanity-check that your burst timing (seconds between events in a 10-30 event burst) resembles something real rather than an arbitrary distribution you invented. That's a real, citable "grounded in production data" claim for your writeup, at low time cost, without making real data sourcing a dependency for your core build.
