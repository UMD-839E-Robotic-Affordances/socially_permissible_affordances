"""Preliminary look at whether the *kind* of reason the model gives goes with whether its judgment was correct.

    python rq1/analyze_why.py [results.json]

Joins two files on (scenario id, prompt type):
  - dataset_with_whys.json: the hand-labeled whys (theme, also, framing); see rq1/WHY_THEMES.md
  - a results file from rq1_experiment.py: the model's answer and `correct` flag
    (default: the newest results file that has why data, searched in rq1/results/ and rq1/results/deprecated/)
The gold label comes from the whys file (a clone of dataset.json).

Samples are not independent: the same scenario appears under every prompt type, so confidence intervals
resample scenarios (cluster bootstrap), and the p-values here are only rough guides.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import chi2_contingency, fisher_exact

ROOT = Path(__file__).resolve().parent.parent
THEMES = ["outcome", "entitlement", "convention", "fit", "no_objection"]
FRAMINGS = ["one_sided", "weighed", "undetermined"]
rng = np.random.default_rng(0)


def newest_results_with_why():
    files = sorted((ROOT / "rq1/results").rglob("rq1_results_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        if json.load(open(f))["config"].get("why_question"):
            return f
    sys.exit("No results file with why data found; pass one explicitly.")


def load(results_path):
    """Join the labeled whys with the results: one row per (scenario, prompt type)."""
    whys = json.load(open(ROOT / "dataset_with_whys.json"))
    results = json.load(open(results_path))["results"]
    rows = []
    for s in whys:
        for pt, w in s["whys"].items():
            r = results[s["id"]][pt]
            rows.append({
                "id": s["id"], "prompt_type": pt, "gold": s["judgment"], "answer": r["answer"], "correct": r["correct"],
                "theme": w["theme"], "also": w["also"], "framing": w["framing"], "n_themes": 1 + len(w["also"]),
            })
    return rows


def cluster_ci(rows, mask_fn, n_boot=2000):
    """Accuracy of the rows selected by mask_fn, with a 95% CI from resampling scenarios."""
    by_scn = defaultdict(list)
    for r in rows:
        by_scn[r["id"]].append(r)
    ids = list(by_scn)
    sel = lambda rs: [r["correct"] for r in rs if mask_fn(r)]
    base = sel(rows)
    if not base:
        return None, 0, (None, None)
    accs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(ids), len(ids))
        v = [c for i in pick for c in sel(by_scn[ids[i]])]
        if v:
            accs.append(np.mean(v))
    lo, hi = np.percentile(accs, [2.5, 97.5])
    return float(np.mean(base)), len(base), (float(lo), float(hi))


def table(rows, title, key, order, indent="  "):
    print(f"\n{title}")
    print(f"{indent}{'':<16}{'n':>5}{'accuracy':>10}   95% CI (scenario bootstrap)")
    for v in order:
        acc, n, (lo, hi) = cluster_ci(rows, lambda r, v=v: key(r) == v)
        if n:
            print(f"{indent}{v:<16}{n:>5}{acc:>10.3f}   [{lo:.2f}, {hi:.2f}]")


def association_test(rows, key, order, label):
    """Chi-square test of independence between a category and correctness (rough: rows are not independent)."""
    vals = [v for v in order if any(key(r) == v for r in rows)]
    obs = np.array([[sum(1 for r in rows if key(r) == v and r["correct"]),
                     sum(1 for r in rows if key(r) == v and not r["correct"])] for v in vals])
    chi2, p, *_ = chi2_contingency(obs)
    print(f"  {label}: chi-square={chi2:.2f}, p={p:.3f} (rows are not independent; treat as a rough guide)")


def main(results_path):
    rows = load(results_path)
    print(f"{results_path}\n{len(rows)} whys, {len({r['id'] for r in rows})} scenarios, overall accuracy {np.mean([r['correct'] for r in rows]):.3f}")

    print("\n1. What themes appear, by prompt type (% of whys)")
    pts = sorted({r["prompt_type"] for r in rows})
    print(f"  {'':<14}" + "".join(f"{p[:10]:>12}" for p in pts))
    for t in THEMES:
        print(f"  {t:<14}" + "".join(f"{100 * sum(1 for r in rows if r['prompt_type'] == p and r['theme'] == t) / sum(1 for r in rows if r['prompt_type'] == p):>11.0f}%" for p in pts))

    table(rows, "2. Accuracy by primary theme", lambda r: r["theme"], THEMES)
    association_test(rows, lambda r: r["theme"], THEMES, "theme vs correctness")

    table(rows, "3. Accuracy by framing", lambda r: r["framing"], FRAMINGS)
    association_test(rows, lambda r: r["framing"], FRAMINGS, "framing vs correctness")

    table(rows, "4. Accuracy by number of considerations (1 = primary only, 2+ = also themes)",
          lambda r: "1" if r["n_themes"] == 1 else "2+", ["1", "2+"])
    a = [r for r in rows if r["n_themes"] == 1]
    b = [r for r in rows if r["n_themes"] > 1]
    odds, p = fisher_exact([[sum(r["correct"] for r in a), sum(not r["correct"] for r in a)],
                            [sum(r["correct"] for r in b), sum(not r["correct"] for r in b)]])
    print(f"  Fisher exact, 1 vs 2+: odds ratio={odds:.2f}, p={p:.3f}")

    print("\n5. Accuracy by theme within each prompt type (does the pattern hold?)")
    print(f"  {'':<14}" + "".join(f"{p[:10]:>12}" for p in pts))
    for t in THEMES:
        cells = []
        for p in pts:
            sub = [r for r in rows if r["prompt_type"] == p and r["theme"] == t]
            cells.append(f"{np.mean([r['correct'] for r in sub]):.2f} ({len(sub)})" if sub else "-")
        print(f"  {t:<14}" + "".join(f"{c:>12}" for c in cells))

    print("\n6. Themes by the true label (counts of whys)")
    golds = ["accept", "reject", "uncertain"]
    print(f"  {'':<14}" + "".join(f"{g:>11}" for g in golds))
    for t in THEMES:
        print(f"  {t:<14}" + "".join(f"{sum(1 for r in rows if r['gold'] == g and r['theme'] == t):>11}" for g in golds))

    print("\n7. Framing against the model's answer (does 'undetermined' reasoning end in 'uncertain'?)")
    answers = ["accept", "reject", "uncertain"]
    print(f"  {'':<14}" + "".join(f"{a:>11}" for a in answers))
    for f in FRAMINGS:
        print(f"  {f:<14}" + "".join(f"{sum(1 for r in rows if r['framing'] == f and r['answer'] == a):>11}" for a in answers))
    u = [r for r in rows if r["framing"] == "undetermined"]
    print(f"  'undetermined' whys that did not answer uncertain: {sum(r['answer'] != 'uncertain' for r in u)} of {len(u)}")

    print("\n8. Mistakes: most common theme among wrong answers, by gold label")
    for g in golds:
        wrong = Counter(r["theme"] for r in rows if r["gold"] == g and not r["correct"])
        right = Counter(r["theme"] for r in rows if r["gold"] == g and r["correct"])
        print(f"  gold {g}: wrong {dict(wrong.most_common())} | right {dict(right.most_common())}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else newest_results_with_why())
