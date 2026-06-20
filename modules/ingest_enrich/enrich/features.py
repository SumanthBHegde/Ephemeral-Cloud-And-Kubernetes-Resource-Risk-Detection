"""Per-event context features (design doc §5).

These are the features that make malicious vs. benign separable when the raw events are
identical (the central thesis). Computed on the full normalized + cohort-assigned table:

  burst_rate            same-action count by same principal in a rolling 5-min window
  principal_novelty     prior appearances of this principal before this event (0 = first)
  is_novel_principal    bool, principal_novelty == 0
  tag_completeness      fraction of the cohort's expected_tags present on the event
  privilege_level       ordinal 0..3 from privileged / host_network / broad RBAC / spot+public
  public_exposure_flag  exposure weighted by resource type (LB normal, bare/debug pod risky)
  exposure_window_s     observed alive seconds (paired create/delete) or session TTL
  off_hours_flag        event hour outside the assigned cohort's active_hours
  cohort_deviation      z-distance from the cohort's EMPIRICAL feature centroid (key feature)

Cohort baselines for the deviation score are computed from the data itself (not the
simulator config) to avoid measuring exactly what was injected.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from modules.data_simulation.generator.build import load_config
from modules.data_simulation.generator.cohorts import load_cohorts

BURST_WINDOW = pd.Timedelta(minutes=5)

# features fed into the cohort-deviation centroid (numeric, behavior-bearing)
_DEVIATION_FEATURES = [
    "burst_rate", "tag_completeness", "privilege_level",
    "public_exposure_flag", "off_hours_flag",
]


def _burst_rate(df: pd.DataFrame) -> pd.Series:
    """Count of same (principal_id, action) events within the trailing 5-min window."""
    out = pd.Series(0, index=df.index, dtype="int64")
    for _, idx in df.groupby(["principal_id", "action"], dropna=False).groups.items():
        sub = df.loc[idx, "event_time"].sort_values()
        # for each event, how many in the same group fall in (t-5min, t]
        times = sub.values.astype("datetime64[ns]")
        counts = np.empty(len(times), dtype="int64")
        lo = 0
        for hi in range(len(times)):
            while times[hi] - times[lo] > BURST_WINDOW.to_timedelta64():
                lo += 1
            counts[hi] = hi - lo + 1
        out.loc[sub.index] = counts
    return out


def _principal_novelty(df: pd.DataFrame) -> pd.Series:
    """Number of prior events by this principal before this one (time-ordered)."""
    order = df["event_time"].argsort(kind="stable")
    novelty = pd.Series(0, index=df.index, dtype="int64")
    seen: dict = {}
    for pos in order:
        idx = df.index[pos]
        pid = df.at[idx, "principal_id"]
        novelty.at[idx] = seen.get(pid, 0)
        seen[pid] = seen.get(pid, 0) + 1
    return novelty


def _tag_completeness(df: pd.DataFrame, expected: dict[str, tuple[str, ...]]) -> pd.Series:
    def frac(row) -> float:
        exp = expected.get(row["cohort"])
        if not exp:
            return np.nan  # no expectation defined for this cohort
        tags = row["tags"] or {}
        labels = row["labels"] or {}
        # tags live on EC2; labels carry the same ownership metadata on K8s objects
        present_keys = set(tags) | set(labels)
        # K8s labels use app.kubernetes.io/managed-by for "managed-by"
        norm = {k.split("/")[-1] for k in present_keys}
        hits = sum(1 for t in exp if t in present_keys or t in norm)
        return hits / len(exp)
    return df.apply(frac, axis=1)


def _privilege_level(df: pd.DataFrame) -> pd.Series:
    lvl = pd.Series(0, index=df.index, dtype="int64")
    lvl += df["privileged"].fillna(False).astype(int)
    lvl += df["host_network"].fillna(False).astype(int)
    lvl += (df["broad_rbac"].fillna(False).astype(int) * 2)
    lvl += (df["is_spot"].fillna(False) & df["public_ip"].notna()).astype(int)
    return lvl.clip(upper=3)


def _public_exposure_flag(df: pd.DataFrame) -> pd.Series:
    """Exposure weighted by resource type: LB public = normal (0.3), bare/debug = risky (1)."""
    flag = pd.Series(0.0, index=df.index, dtype="float64")
    # cloud: spot+public IP staging
    flag = flag.mask(df["public_ip"].notna(), 0.6)
    # k8s service exposure
    lb = (df["service_type"] == "LoadBalancer") & df["exposed_open"]
    nodeport = (df["service_type"] == "NodePort") & df["exposed_open"]
    flag = flag.mask(lb, 0.3)            # public LB is the expected, normal case
    flag = flag.mask(nodeport, 1.0)      # NodePort 0.0.0.0/0 is the debug-pod danger
    # bare privileged pod is itself an exposure even without a service
    bare_priv = (df["controller_owner"].isna()) & (df["privileged"]) & (df["action"] == "pod_create")
    flag = flag.mask(bare_priv, np.maximum(flag, 0.8))
    return flag


def _off_hours_flag(df: pd.DataFrame, active: dict[str, tuple[int, int]]) -> pd.Series:
    hours = df["event_time"].dt.hour

    def off(row_hour, cohort) -> int:
        win = active.get(cohort)
        if not win:
            return 0
        start, end = win
        inside = start <= row_hour < end
        return 0 if inside else 1
    return pd.Series(
        [off(h, c) for h, c in zip(hours, df["cohort"])],
        index=df.index, dtype="int64")


def _exposure_window(df: pd.DataFrame) -> pd.Series:
    """Observed alive seconds: pod create->delete pairing per (namespace,resource), else TTL."""
    out = pd.Series(np.nan, index=df.index, dtype="float64")
    # session TTL straight through where present
    out = out.mask(df["session_ttl"].notna(), df["session_ttl"].astype("float64"))
    # pod lifetime: match each create to the next delete of the same ns+name
    pods = df[df["action"].isin(["pod_create", "pod_delete"])]
    for (ns, name), grp in pods.groupby(["namespace", "resource_id"], dropna=False):
        g = grp.sort_values("event_time")
        create_t = None
        create_idx = None
        for idx, r in g.iterrows():
            if r["action"] == "pod_create":
                create_t, create_idx = r["event_time"], idx
            elif r["action"] == "pod_delete" and create_t is not None:
                out.at[create_idx] = (r["event_time"] - create_t).total_seconds()
                create_t = None
    return out


def _cohort_deviation(df: pd.DataFrame) -> pd.Series:
    """Per-cohort z-distance from the cohort's empirical centroid over behavior features."""
    feats = df[_DEVIATION_FEATURES].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    dev = pd.Series(0.0, index=df.index, dtype="float64")
    for cohort, idx in df.groupby("cohort").groups.items():
        block = feats.loc[idx]
        mu = block.mean()
        sd = block.std(ddof=0).replace(0, 1.0)
        z = (block - mu) / sd
        dev.loc[idx] = np.sqrt((z ** 2).sum(axis=1))  # Euclidean distance in z-space
    return dev


def add_features(df: pd.DataFrame, config_path: str | None = None) -> pd.DataFrame:
    """Return a copy of the cohort-assigned table with all §5 feature columns added."""
    cfg = load_config(config_path)
    cohorts = load_cohorts(cfg["cohorts"])
    expected = {n: c.expected_tags for n, c in cohorts.items()}
    active = {n: c.active_hours for n, c in cohorts.items()}

    df = df.copy()
    df["burst_rate"] = _burst_rate(df)
    df["principal_novelty"] = _principal_novelty(df)
    df["is_novel_principal"] = df["principal_novelty"] == 0
    df["tag_completeness"] = _tag_completeness(df, expected)
    df["privilege_level"] = _privilege_level(df)
    df["public_exposure_flag"] = _public_exposure_flag(df)
    df["exposure_window_s"] = _exposure_window(df)
    df["off_hours_flag"] = _off_hours_flag(df, active)
    df["cohort_deviation"] = _cohort_deviation(df)
    return df
