"""Extended RQ1 analysis of one run_all.sh run (both models, same tag). Run:

    python rq1/analysis_extended.py rq1/results/rq1_results_claude-haiku-...json rq1/results/rq1_results_claude-sonnet-...json

Reuses load() / mcnemar_exact() / bootstrap_diff() from analysis.py. Writes a text report and a JSON file next to the
results (rq1/results/rq1_extended_analysis_<tag>.txt/.json). It only reads files; nothing is sent to a model.
Everything here is descriptive or a paired test: the data is one seed and one run per model, so small differences
(a few scenarios) are not evidence of an effect.
"""
import json
import sys
from collections import Counter, defaultdict
from math import sqrt
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import LABELS, ROOT, bootstrap_diff, load, mcnemar_exact  # noqa: E402

OUT = []
JSON = {}


def p(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    OUT.append(line)


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main(paths):
    dataset = {d["id"]: d for d in json.load(open(ROOT / "dataset.json"))}
    cats = json.load(open(ROOT / "dataset_review" / "categories.json"))["categories"]
    group_of = {k: v["group"] for k, v in cats.items()}
    runs = {}
    for path in paths:
        cfg, ids, y, pred, chars = load(path)
        short = cfg["model"].replace("claude-", "").replace("-5-5", "")
        whys = json.load(open(str(path).replace("rq1_results_", "rq1_whys_")))["whys"]
        runs[short] = dict(cfg=cfg, ids=ids, y=y, pred=pred, whys=whys, path=path,
                           ok={t: pred[t] == y for t in pred})
    models = list(runs)
    types = runs[models[0]]["cfg"]["prompt_types"]
    ids = runs[models[0]]["ids"]
    y = runs[models[0]]["y"]
    assert all(r["ids"] == ids for r in runs.values()), "runs cover different scenarios"
    n = len(ids)
    tags = {i: dataset[i]["tags"] for i in ids}
    p(f"Extended analysis of {n} scenarios, models: {', '.join(models)}, prompt types: {', '.join(types)}")
    p("Gold labels:", {k: int(v) for k, v in Counter(y.tolist()).items()}, "| always-reject baseline:", round((y == "reject").mean(), 3))

    # 1. Model comparison
    p("\n== 1. Haiku vs Sonnet (paired by scenario) ==")
    if len(models) == 2:
        a, b = models
        JSON["model_comparison"] = {}
        for t in types:
            f, br, pv = mcnemar_exact(runs[a]["ok"][t], runs[b]["ok"][t])
            accs = [float(runs[m]["ok"][t].mean()) for m in (a, b)]
            p(f"  {t:17s} {a}={accs[0]:.3f} {b}={accs[1]:.3f}  {b} fixed {f}, broke {br} vs {a}, McNemar p={pv:.3f}")
            JSON["model_comparison"][t] = dict(acc=dict(zip((a, b), accs)), fixed=f, broke=br, p=pv)
        pooled_a = np.concatenate([runs[a]["ok"][t] for t in types]); pooled_b = np.concatenate([runs[b]["ok"][t] for t in types])
        f, br, pv = mcnemar_exact(pooled_a, pooled_b)
        p(f"  pooled over all {len(types)} prompt types ({len(pooled_a)} answers each): {a}={pooled_a.mean():.3f} {b}={pooled_b.mean():.3f}, "
          f"{b} fixed {f}, broke {br}, McNemar p={pv:.4f} (answers of one scenario are not independent, so treat p as optimistic)")

    # 2. Confusion matrices
    p("\n== 2. Confusion matrices (rows = gold, columns = model answer: accept / reject / uncertain) ==")
    JSON["confusion"] = {}
    for m in models:
        for t in types:
            M = np.array([[int(((y == g) & (runs[m]["pred"][t] == a_)).sum()) for a_ in LABELS] for g in LABELS])
            p(f"  {m:7s} {t:17s} " + " | ".join(f"{g}: {' '.join(f'{v:3d}' for v in row)}" for g, row in zip(LABELS, M)))
            JSON["confusion"][f"{m}/{t}"] = M.tolist()
        # answers outside the three labels
        extra = Counter(x for t in types for x in runs[m]["pred"][t] if x not in LABELS)
        if extra:
            p(f"  {m}: answers outside the three labels: {dict(extra)}")

    # 3. Accuracy by gold class
    p("\n== 3. Accuracy by gold label (recall of each class) ==")
    for m in models:
        for g in LABELS:
            mask = y == g
            p(f"  {m:7s} gold={g:9s} (n={int(mask.sum()):3d}) " + "  ".join(f"{t}={runs[m]['ok'][t][mask].mean():.2f}" for t in types))

    # 4. Accuracy by tag and by group
    p("\n== 4. Accuracy by tag (scenarios can have several tags; mean = accuracy over all 5 prompt types, with its Wilson 95% CI; sorted worst first; n is small for many tags) ==")
    tag_counter = Counter(t for i in ids for t in tags[i])
    JSON["by_tag"] = {}
    for m in models:
        p(f"  -- {m}")
        rows = []
        for tg, cnt in tag_counter.items():
            mask = np.array([tg in tags[i] for i in ids])
            per_type = {t: float(runs[m]["ok"][t][mask].mean()) for t in types}
            mean_acc = float(np.mean(list(per_type.values())))
            k = int(sum(runs[m]["ok"][t][mask].sum() for t in types))
            lo, hi = wilson(k, int(mask.sum()) * len(types))
            rows.append((mean_acc, tg, cnt, per_type, lo, hi))
            JSON["by_tag"].setdefault(m, {})[tg] = dict(n=cnt, per_type=per_type, mean=mean_acc, ci=[lo, hi])
        for mean_acc, tg, cnt, per_type, lo, hi in sorted(rows):
            p(f"  {tg:20s} n={cnt:2d} mean={mean_acc:.2f} [{lo:.2f},{hi:.2f}]  " + " ".join(f"{t[:6]}={v:.2f}" for t, v in per_type.items()))
    p("\n  By group (Physical / Coordination / Social; a scenario counts once per group it has a tag in):")
    JSON["by_group"] = {}
    for m in models:
        for grp in ("Physical", "Coordination", "Social"):
            mask = np.array([any(group_of.get(tg) == grp for tg in tags[i]) for i in ids])
            per_type = {t: float(runs[m]["ok"][t][mask].mean()) for t in types}
            p(f"  {m:7s} {grp:12s} n={int(mask.sum()):3d} " + " ".join(f"{t[:6]}={v:.2f}" for t, v in per_type.items()))
            JSON["by_group"].setdefault(m, {})[grp] = dict(n=int(mask.sum()), per_type=per_type)

    # 5. Prompt-type effects beyond "none"
    p("\n== 5. Paired prompt-type comparisons (fixed = wrong under the first, right under the second) ==")
    pairs = [("examples", "examples_nolabel"), ("taxonomy", "tax+ex"), ("examples", "tax+ex"), ("none", "tax+ex")]
    JSON["prompt_pairs"] = {}
    for m in models:
        for a_, b_ in pairs:
            f, br, pv = mcnemar_exact(runs[m]["ok"][a_], runs[m]["ok"][b_])
            lo, hi = bootstrap_diff(y, runs[m]["pred"][a_], runs[m]["pred"][b_], lambda yy, pp: float((yy == pp).mean()))
            p(f"  {m:7s} {a_:17s} -> {b_:17s} fixed={f:2d} broke={br:2d} p={pv:.3f} gain CI [{lo:+.3f},{hi:+.3f}]")
            JSON["prompt_pairs"][f"{m}/{a_}->{b_}"] = dict(fixed=f, broke=br, p=pv, ci=[lo, hi])

    # 6. Example effects
    p("\n== 6. The single shown example: does its label / tag overlap matter? ('examples' prompt) ==")
    JSON["example_effects"] = {}
    for m in models:
        sel = runs[m]["cfg"]["selected_examples"]
        same_label = np.array([dataset[sel[i]]["judgment"] == dataset[i]["judgment"] for i in ids])
        overlap = np.array([len(set(dataset[sel[i]]["tags"]) & set(tags[i])) for i in ids])
        for t in ("examples", "examples_nolabel", "tax+ex"):
            ok, base = runs[m]["ok"][t], runs[m]["ok"]["none"]
            p(f"  {m:7s} {t:17s} example label == gold (n={int(same_label.sum())}): acc {ok[same_label].mean():.2f} vs 'none' {base[same_label].mean():.2f}; "
              f"label != gold (n={int((~same_label).sum())}): acc {ok[~same_label].mean():.2f} vs 'none' {base[~same_label].mean():.2f}")
            JSON["example_effects"][f"{m}/{t}"] = dict(
                same_label=dict(n=int(same_label.sum()), acc=float(ok[same_label].mean()), none=float(base[same_label].mean())),
                diff_label=dict(n=int((~same_label).sum()), acc=float(ok[~same_label].mean()), none=float(base[~same_label].mean())))
        copied = np.mean([runs[m]["pred"]["examples"][k] == dataset[sel[i]]["judgment"] for k, i in enumerate(ids)])
        p(f"  {m:7s} how often the 'examples' answer equals the example's label: {copied:.2f} (the example's label equals the gold label for {same_label.mean():.2f} of scenarios, so ~{same_label.mean():.2f} is what you would see with no copying at all)")
        for ov in sorted(set(overlap)):
            mk = overlap == ov
            p(f"  {m:7s} example shares {ov} tag(s) with the scenario (n={int(mk.sum()):3d}): acc examples {runs[m]['ok']['examples'][mk].mean():.2f}, none {runs[m]['ok']['none'][mk].mean():.2f}")

    # 7. Stability across prompt types
    p("\n== 7. Stability: how often the answer changes with the prompt type ==")
    JSON["stability"] = {}
    for m in models:
        P = np.array([runs[m]["pred"][t] for t in types])  # types x scenarios
        distinct = np.array([len(set(P[:, k])) for k in range(n)])
        p(f"  {m:7s} all 5 prompts give the same answer on {int((distinct == 1).sum())}/{n} scenarios; 2 different answers on {int((distinct == 2).sum())}; 3 on {int((distinct == 3).sum())}")
        allok = np.array([all(runs[m]["ok"][t][k] for t in types) for k in range(n)])
        anyok = np.array([any(runs[m]["ok"][t][k] for t in types) for k in range(n)])
        p(f"  {m:7s} right under all prompts: {int(allok.sum())}, right under some: {int((anyok & ~allok).sum())}, wrong under all: {int((~anyok).sum())}")
        JSON["stability"][m] = dict(same=int((distinct == 1).sum()), all_right=int(allok.sum()), some_right=int((anyok & ~allok).sum()), none_right=int((~anyok).sum()))
        # share of the five-prompt disagreement by gold label
        flip = distinct > 1
        p(f"  {m:7s} unstable scenarios by gold label: " + ", ".join(f"{g}={int((flip & (y == g)).sum())}/{int((y == g).sum())}" for g in LABELS))

    # 8. Hard scenarios
    p("\n== 8. Scenarios wrong under every prompt type, for each model, and for both ==")
    wrong_all = {m: {ids[k] for k in range(n) if not any(runs[m]["ok"][t][k] for t in types)} for m in models}
    both = set.intersection(*wrong_all.values())
    JSON["hard"] = {m: sorted(v) for m, v in wrong_all.items()}
    JSON["hard"]["both"] = sorted(both)
    for m in models:
        p(f"  {m}: {len(wrong_all[m])} scenarios: {', '.join(sorted(wrong_all[m]))}")
    p(f"  wrong under every prompt in BOTH models: {len(both)}")
    for i in sorted(both):
        d = dataset[i]
        answers = {m: str(Counter(str(runs[m]["pred"][t][ids.index(i)]) for t in types).most_common(1)[0][0]) for m in models}
        p(f"    {i} gold={d['judgment']:9s} answers={answers} tags={d['tags']} | {d['action']} {d['object']} | {d['context'][:110]}")
    p("  gold labels of the scenarios wrong under every prompt in both models:", dict(Counter(dataset[i]["judgment"] for i in both)))

    # 9. Why factors
    p("\n== 9. The model's stated factors ('why'), counted as written (lowercased; not grouped into categories) ==")
    JSON["why_factors"] = {}
    for m in models:
        allc, wrongc = Counter(), Counter()
        for k, i in enumerate(ids):
            for t in types:
                w = runs[m]["whys"].get(i, {}).get(t)
                if not w or not w.get("parsed"):
                    continue
                for fct in w["parsed"].get("factors", []):
                    allc[str(fct).strip().lower()] += 1
                    if not runs[m]["ok"][t][k]:
                        wrongc[str(fct).strip().lower()] += 1
        p(f"  {m}: {sum(allc.values())} factor mentions, {len(allc)} distinct labels; most common: " + ", ".join(f"{f} {c}" for f, c in allc.most_common(15)))
        p(f"  {m}: most common among WRONG answers: " + ", ".join(f"{f} {c}" for f, c in wrongc.most_common(12)))
        JSON["why_factors"][m] = dict(distinct=len(allc), top=allc.most_common(30), top_wrong=wrongc.most_common(30))

    # 10. Cost
    p("\n== 10. Token use ==")
    for m in models:
        u = runs[m]["cfg"]["usage"]
        p(f"  {m}: {u['calls']} calls, {u['input_tokens']:,} input tokens, {u['output_tokens']:,} output tokens")

    tag = Path(paths[0]).stem.split("_low_")[-1]
    outdir = Path(paths[0]).parent
    (outdir / f"rq1_extended_analysis_{tag}.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    (outdir / f"rq1_extended_analysis_{tag}.json").write_text(json.dumps(JSON, indent=1, default=str), encoding="utf-8")
    print(f"\nWrote {outdir / f'rq1_extended_analysis_{tag}.txt'} and .json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
