"""Sketch of the RQ1 statistics. Run:  python rq1/analysis.py rq1/results/<file>.json

Everything is paired: the same scenarios are scored under every prompt type, so
we compare prompt types with paired tests, not independent-sample tests.
Placeholders marked TODO are meant to be filled in once more runs exist.
"""
import json
import sys
from math import comb
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parent.parent
LABELS = ["accept", "reject", "uncertain"]


def load(path):
    data = json.load(open(path))
    truth = {d["id"]: d["judgment"] for d in json.load(open(ROOT / "dataset.json"))}
    ids = sorted(data["results"])
    y = np.array([truth[i] for i in ids])
    types = data["config"]["prompt_types"]
    pred = {t: np.array([data["results"][i][t]["answer"] for i in ids]) for t in types}
    chars = {t: np.array([data["results"][i][t].get("prompt_chars", np.nan) for i in ids]) for t in types}
    return data["config"], ids, y, pred, chars


def mcnemar_exact(a_correct, b_correct):
    """Two-sided exact McNemar on paired correctness: (fixed, broke, p)."""
    fixed = int((~a_correct & b_correct).sum())
    broke = int((a_correct & ~b_correct).sum())
    n = fixed + broke
    if n == 0:
        return fixed, broke, 1.0
    p = min(1.0, 2 * sum(comb(n, k) for k in range(min(fixed, broke) + 1)) / 2**n)
    return fixed, broke, p


def bootstrap_diff(y, pa, pb, metric, n_boot=5000, seed=0):
    """95% CI of metric(B) - metric(A), resampling scenarios (paired)."""
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        diffs.append(metric(y[i], pb[i]) - metric(y[i], pa[i]))
    return tuple(np.percentile(diffs, [2.5, 97.5]))


def acc(y, p):
    return float((y == p).mean())


def main(path):
    config, ids, y, pred, chars = load(path)
    types = config["prompt_types"]
    print(f"{path}\nmodel={config['model']} effort={config['effort']} n={len(ids)}")

    print("\n1. Headline (always-reject baseline: %.3f)" % acc(y, np.array(["reject"] * len(y))))
    for t in types:
        n_invalid = int((pred[t] == "invalid").sum())
        print(f"  {t:<9} acc={acc(y, pred[t]):.3f} bal_acc={balanced_accuracy_score(y, pred[t]):.3f} invalid={n_invalid}")

    print("\n2. Per-class precision / recall / F1 (reject focus)")
    for t in types:
        p, r, f, _ = precision_recall_fscore_support(y, pred[t], labels=LABELS, zero_division=0)
        print(f"  {t:<9} " + "  ".join(f"{l}: P{p[k]:.2f} R{r[k]:.2f} F{f[k]:.2f}" for k, l in enumerate(LABELS)))

    print("\n3. Paired comparisons vs baseline 'none' (McNemar exact; bootstrap 95% CI of acc gain)")
    base = types[0]
    for t in types[1:]:
        fixed, broke, p = mcnemar_exact(pred[base] == y, pred[t] == y)
        lo, hi = bootstrap_diff(y, pred[base], pred[t], acc)
        print(f"  {base} -> {t:<9} fixed={fixed} broke={broke} p={p:.3f}  gain CI [{lo:+.3f}, {hi:+.3f}]")
    # TODO: also compare taxonomy vs examples vs tax+ex pairwise; correct for multiple comparisons (Holm).

    print("\n4. Prompt length vs correctness (prompt_chars saved per call)")
    for t in types:
        c = chars[t]
        if np.isnan(c).any():
            print(f"  {t:<9} no prompt_chars in this file")
        else:
            print(f"  {t:<9} chars={int(c.mean())}")
    # TODO: scenario-level length (scenario text length) vs correctness: logistic regression / point-biserial.

    # TODO: accuracy by dataset tag (ownership, privacy, ...) and by reviewed flag; needs tags from dataset.json.
    # TODO: variance across repeated runs (several results files) -> mean +- sd per metric.


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "rq1/results/rq1_results_claude-haiku-5-5_low.json")
