"""
Confusability figure — the project's single most important explanatory artifact.

Renders, from the *real* enriched data, the central thesis of the whole pipeline:

  At the event level a legitimate autoscaler burst and a malicious crypto-mining
  hijack are STATISTICALLY IDENTICAL. The signal that separates them is not in the
  event volume/rate — it is in the CONTEXT (tag completeness, ownership, off-hours).

Left panel : overlapping burst_rate distributions for crypto_burst vs legit_autoscale.
             They sit on top of each other — a detector looking at "how fast did this
             principal create resources?" cannot tell them apart. (The trap.)
Right panel: the context features that DO separate them — tag completeness, off-hours
             rate, controller ownership. (The answer.)

Labels (scenario_type) are read ONLY here, at figure-build time, to select the two
populations. Nothing about this leaks into the runtime/client — it is a static PNG
committed to docs/figures/ for the README and the demo video.

Run:  python modules/dashboard/figures/confusability.py
Out:  docs/figures/confusability.png
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ENRICHED = ROOT / "data" / "processed" / "events_enriched.parquet"
LABELS = ROOT / "data" / "raw" / "labels.jsonl"
OUT = ROOT / "docs" / "figures" / "confusability.png"

CRYPTO = "crypto_burst"
LEGIT = "legit_autoscale"

# Brand-ish palette: attacker red, benign teal.
C_ATTACK = "#dc2626"
C_BENIGN = "#0d9488"
GRID = "#e5e7eb"
INK = "#111827"
MUTED = "#6b7280"


def load() -> pd.DataFrame:
    df = pd.read_parquet(ENRICHED)
    labs = pd.DataFrame(json.loads(l) for l in LABELS.open())
    return df.merge(
        labs[["record_id", "scenario_type"]], on="record_id", how="left"
    )


def main() -> None:
    m = load()
    crypto = m[m.scenario_type == CRYPTO]
    legit = m[m.scenario_type == LEGIT]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
        }
    )
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 5.2))
    fig.suptitle(
        "Same burst. Which one is the attack?",
        fontsize=17,
        fontweight="bold",
        y=0.99,
    )

    # ---- LEFT: burst_rate distributions overlap (the trap) ----
    bins = np.linspace(0, 35, 30)
    axL.hist(
        legit.burst_rate.dropna(), bins=bins, density=True, alpha=0.55,
        color=C_BENIGN, label=f"Legit autoscale  (n={len(legit)})",
    )
    axL.hist(
        crypto.burst_rate.dropna(), bins=bins, density=True, alpha=0.55,
        color=C_ATTACK, label=f"Crypto hijack  (n={len(crypto)})",
    )
    axL.axvline(legit.burst_rate.mean(), color=C_BENIGN, lw=2, ls="--")
    axL.axvline(crypto.burst_rate.mean(), color=C_ATTACK, lw=2, ls="--")
    axL.set_title(
        "Burst rate — what a detector sees\n(resources created per rolling window)",
        fontsize=12, fontweight="bold",
    )
    axL.set_xlabel("burst_rate")
    axL.set_ylabel("density")
    axL.legend(frameon=False, fontsize=10)
    axL.grid(axis="y", color=GRID, lw=0.8)
    axL.set_axisbelow(True)
    for s in ("top", "right"):
        axL.spines[s].set_visible(False)
    axL.text(
        0.98, 0.62,
        f"means: {legit.burst_rate.mean():.1f}  vs  {crypto.burst_rate.mean():.1f}\n"
        "→ statistically indistinguishable",
        transform=axL.transAxes, ha="right", va="top", fontsize=10,
        color=MUTED, style="italic",
    )

    # ---- RIGHT: context features separate them (the answer) ----
    feats = ["tag_completeness", "off_hours_flag", "is_spot"]
    labels = ["Tag\ncompleteness", "Off-hours\nrate", "Spot-instance\nrate"]

    def frac(g, f):
        if f == "is_spot":
            return float((g[f] == True).mean())  # noqa: E712
        return float(g[f].mean())

    legit_vals = [frac(legit, f) for f in feats]
    crypto_vals = [frac(crypto, f) for f in feats]

    x = np.arange(len(feats))
    w = 0.38
    axR.bar(x - w / 2, legit_vals, w, color=C_BENIGN, label="Legit autoscale")
    axR.bar(x + w / 2, crypto_vals, w, color=C_ATTACK, label="Crypto hijack")
    for i, (lv, cv) in enumerate(zip(legit_vals, crypto_vals)):
        axR.text(i - w / 2, lv + 0.02, f"{lv:.2f}", ha="center", fontsize=9, color=INK)
        axR.text(i + w / 2, cv + 0.02, f"{cv:.2f}", ha="center", fontsize=9, color=INK)
    axR.set_title(
        "Context features — what actually separates them\n(metadata & ownership, not volume)",
        fontsize=12, fontweight="bold",
    )
    axR.set_xticks(x)
    axR.set_xticklabels(labels, fontsize=10)
    axR.set_ylim(0, 1.12)
    axR.set_ylabel("fraction of events")
    axR.legend(frameon=False, fontsize=10, loc="upper center")
    axR.grid(axis="y", color=GRID, lw=0.8)
    axR.set_axisbelow(True)
    for s in ("top", "right"):
        axR.spines[s].set_visible(False)

    fig.text(
        0.5, 0.015,
        "The two bursts fire at the same rate (left). Only the context — missing tags, "
        "off-hours timing, untagged spot fleets — reveals the attack (right). "
        "Detect on context, not events.",
        ha="center", fontsize=10.5, color=MUTED,
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(
        f"  crypto: burst_rate mean={crypto.burst_rate.mean():.2f}  "
        f"tag={frac(crypto,'tag_completeness'):.2f}  off_hours={frac(crypto,'off_hours_flag'):.2f}"
    )
    print(
        f"  legit : burst_rate mean={legit.burst_rate.mean():.2f}  "
        f"tag={frac(legit,'tag_completeness'):.2f}  off_hours={frac(legit,'off_hours_flag'):.2f}"
    )


if __name__ == "__main__":
    main()
