"""When does the model's "why" go with a correct prediction? Hypothesis search over one run_all.sh run. Run:

    python rq1/analysis_why.py rq1/results/rq1_results_claude-haiku-...json rq1/results/rq1_results_claude-sonnet-...json

Method (scientific method, no model calls, reads files only):
  1. Each hypothesis is a feature of the "why" (reason + factors) plus an optional subset of answers (e.g. only
     scenarios whose gold label is accept) and a predicted direction for "the answer is correct".
  2. EXPLORE: AUC on every other scenario (even index), Haiku and Sonnet separately. AUC 0.5 = no signal; below 0.5
     means a higher feature value goes with WRONG answers.
  3. HELD-OUT: the other scenarios (odd index). A hypothesis is SUPPORTED only if, on the held-out half, both models
     show AUC at least 0.06 away from 0.5 in the predicted direction, the cluster-bootstrap (by scenario) 95% interval
     of at least the pooled held-out AUC excludes 0.5, and the explore half had the same direction.
  4. Every hypothesis tried is listed, supported or not, so the number of tries is visible (many tries make a lucky
     result likely; that is why the held-out half and both models are required).
Answers come from the three prompts that do not show the taxonomy (none, examples, examples_nolabel): the taxonomy
prompts make the model copy category names into its factors, so factor vocabulary there says nothing about reasoning.
Writes rq1/results/rq1_why_analysis_<tag>.txt and .json next to the results. One seed and one run per model.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analysis import ROOT  # noqa: E402

NT = ("none", "examples", "examples_nolabel")
ALL_TYPES = ("none", "taxonomy", "examples", "examples_nolabel", "tax+ex")
STOP = set("the a an and or of to in on is are was were be it its this that for with as by at from not no so if but than then there "
           "their they them he she his her robot human user can will would should does do did has have had into over under about "
           "which who whom while when what because without".split())
W = lambda s: re.findall(r"[a-z]+", s.lower())
tok = lambda s: {w for w in W(s) if w not in STOP and len(w) > 2}
LEX = {
    "hedge": "may might could depends depend unclear unknown unless possibly whether missing assume assuming unspecified uncertain ambiguous perhaps likely probably potentially",
    "risk": "risk risks danger dangerous harm unsafe damage damaged hazard injury fall burn break breakage spill hurt unstable fragile",
    "permission": "permission consent authorization authorized unauthorized asking asked owner ownership belongs property entitled",
    "mitigation": "alternative alternatives available cheap reversible minimal negligible nobody unoccupied empty replaceable harmless trivial safely low",
    "rule": "rule rules law policy posted limit regulation norm norms protocol",
    "negation": "not no without never cannot nor neither",
    "contrast": "but although however though while despite yet whereas",
}
LEX = {k: set(v.split()) for k, v in LEX.items()}


def load(path):
    cfg_res = json.load(open(path))
    whys = json.load(open(str(path).replace("rq1_results_", "rq1_whys_")))["whys"]
    ds = {d["id"]: d for d in json.load(open(ROOT / "dataset.json"))}
    short = cfg_res["config"]["model"].replace("claude-", "").replace("-5-5", "")
    ids = sorted(cfg_res["results"])
    rows = []
    for idx, i in enumerate(ids):
        d = ds[i]
        scen = tok(" ".join([d["context"], d["action"], d["object"], d["goal"]]))
        fsets = {t: tok(" ".join(map(str, whys[i][t]["parsed"]["factors"]))) for t in ALL_TYPES}
        for t in ALL_TYPES:
            p = whys[i][t]["parsed"]
            words = W(p["reason"]) + W(" ".join(map(str, p["factors"])))
            rs = tok(p["reason"])
            others = [fsets[u] for u in ALL_TYPES if u != t]
            feat = {k: sum(w in lex for w in words) for k, lex in LEX.items()}
            feat.update(
                length=len(p["reason"].split()), n_factors=len(p["factors"]),
                digits=int(bool(re.search(r"\d", p["reason"]))),
                factor_consistency=float(np.mean([len(fsets[t] & o) / max(len(fsets[t] | o), 1) for o in others])),
                scenario_overlap=len(rs & scen) / max(len(rs), 1),
                hedge_but_not_uncertain=int(feat["hedge"] > 0 and cfg_res["results"][i][t]["answer"] != "uncertain"),
                factor_tokens=fsets[t],
            )
            rows.append(dict(model=short, id=i, idx=idx, t=t, gold=d["judgment"], ans=cfg_res["results"][i][t]["answer"],
                             ok=bool(cfg_res["results"][i][t]["correct"]), feat=feat))
    return short, rows


def auc(rows, f):
    y = [r["ok"] for r in rows]
    if len(set(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, [f(r) for r in rows]))


def boot_ci(rows, f, n_boot=400, seed=0):
    rng = np.random.default_rng(seed)
    by = {}
    for r in rows:
        by.setdefault(r["id"], []).append(r)
    keys = list(by)
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        v = auc([r for k in pick for r in by[keys[k]]], f)
        if v == v:
            vals.append(v)
    return tuple(np.percentile(vals, [2.5, 97.5])) if vals else (float("nan"), float("nan"))


# (name, plain-language hypothesis, feature function of a row, subset predicate, expected direction: -1 higher feature = wrong, +1 = right)
HYPS = [
    ("H1 hedging", "A why with hedging words signals an ambiguous case; ambiguous cases are answered wrongly more often.",
     lambda r: r["feat"]["hedge"], lambda r: True, -1),
    ("H1b long reason", "A longer why signals a harder case; harder cases are answered wrongly more often.",
     lambda r: r["feat"]["length"], lambda r: True, -1),
    ("H2 hedge but committed", "A why that hedges while the answer is accept/reject (not uncertain) is a doubt the model overrode.",
     lambda r: r["feat"]["hedge_but_not_uncertain"], lambda r: True, -1),
    ("H3 risk talk on gold-accept", "On scenarios whose gold is accept, risk/danger words in the why explain over-caution (wrong).",
     lambda r: r["feat"]["risk"], lambda r: r["gold"] == "accept", -1),
    ("H4 mitigation talk on gold-accept", "On gold-accept scenarios, citing mitigating facts (alternatives, cheap, reversible) goes with the right answer.",
     lambda r: r["feat"]["mitigation"], lambda r: r["gold"] == "accept", +1),
    ("H5 permission talk on gold-reject", "On gold-reject scenarios, citing permission/consent/ownership goes with the right answer.",
     lambda r: r["feat"]["permission"], lambda r: r["gold"] == "reject", +1),
    ("H6 rule talk", "Citing an explicit rule makes the model rigid: wrong when the gold is uncertain or accept.",
     lambda r: r["feat"]["rule"], lambda r: r["gold"] != "reject", -1),
    ("H7 contrast words", "A why that weighs a 'but/although' consideration is balancing, which goes with the right answer.",
     lambda r: r["feat"]["contrast"], lambda r: True, +1),
    ("H8 factor consistency across prompts", "If the factors named barely change across the five prompts, the model is sure, and right.",
     lambda r: r["feat"]["factor_consistency"], lambda r: True, +1),
    ("H9 scenario overlap", "A why that reuses the scenario's own words is grounded in its facts, and right.",
     lambda r: r["feat"]["scenario_overlap"], lambda r: True, +1),
    ("H10 negation", "Negation-heavy reasons ('no permission', 'without asking') are reject-leaning and wrong on gold accept/uncertain.",
     lambda r: r["feat"]["negation"], lambda r: r["gold"] != "reject", -1),
]


def main(paths):
    runs = dict(load(p) for p in paths)
    models = list(runs)
    OUT, JSON = [], {"hypotheses": []}

    def p(*a):
        line = " ".join(str(x) for x in a)
        print(line)
        OUT.append(line)

    p("When does the 'why' go with a correct prediction? Hypothesis search (answers from prompts without the taxonomy: " + ", ".join(NT) + ")")
    p("AUC = chance a right answer has a HIGHER feature value than a wrong one (0.5 none; <0.5 higher value = wrong). EXPLORE = even-indexed scenarios, HELD-OUT = odd-indexed.\n")
    supported = []
    for name, text, fn, subset, direction in HYPS:
        p(f"== {name}: {text}\n   expected direction: {'higher value -> right (AUC > 0.5)' if direction > 0 else 'higher value -> wrong (AUC < 0.5)'}")
        rec = {"name": name, "hypothesis": text, "expected_direction": direction, "models": {}}
        passed = True
        held_all = []
        for m in models:
            rows = [r for r in runs[m] if r["t"] in NT and subset(r)]
            expl = [r for r in rows if r["idx"] % 2 == 0]
            held = [r for r in rows if r["idx"] % 2 == 1]
            held_all += held
            ae, ah = auc(expl, fn), auc(held, fn)
            lo, hi = boot_ci(held, fn)
            n_pos = sum(r["ok"] for r in held)
            p(f"   {m:7s} explore AUC={ae:.2f} (n={len(expl)}) | held-out AUC={ah:.2f} (n={len(held)}, {n_pos} right) bootstrap 95% CI [{lo:.2f},{hi:.2f}]")
            rec["models"][m] = dict(explore_auc=ae, held_auc=ah, n_explore=len(expl), n_held=len(held), held_ci=[lo, hi])
            ok_dir = (ah - 0.5) * direction >= 0.06 and (ae - 0.5) * direction > 0
            passed &= bool(ok_dir)
        lo, hi = boot_ci(held_all, fn)
        pooled = auc(held_all, fn)
        ci_ok = (lo > 0.5) if direction > 0 else (hi < 0.5)
        p(f"   pooled held-out (both models) AUC={pooled:.2f} bootstrap 95% CI [{lo:.2f},{hi:.2f}]")
        verdict = "SUPPORTED" if passed and ci_ok else "NOT SUPPORTED"
        p(f"   -> {verdict}\n")
        rec.update(pooled_held_auc=pooled, pooled_ci=[lo, hi], verdict=verdict)
        JSON["hypotheses"].append(rec)
        if verdict == "SUPPORTED":
            supported.append(name)

    # H12: are consistency (H8) and overlap (H9) just restatements of hedging and length? Fit on explore, test on held-out.
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    p("== H12 incremental value: do consistency and overlap add to hedging + length? (logistic regression fit on EXPLORE scenarios, AUC on HELD-OUT) ==")
    sets = {"hedge+length": ["hedge", "length"], "consistency+overlap": ["factor_consistency", "scenario_overlap"],
            "all four": ["hedge", "length", "factor_consistency", "scenario_overlap"]}
    JSON["h12"] = {}
    for m in models:
        rows = [r for r in runs[m] if r["t"] in NT]
        tr = [r for r in rows if r["idx"] % 2 == 0]
        te = [r for r in rows if r["idx"] % 2 == 1]
        X = lambda rs, fs: np.array([[r["feat"][f] for f in fs] for r in rs], dtype=float)
        line = []
        for name, fs in sets.items():
            sc = StandardScaler().fit(X(tr, fs))
            clf = LogisticRegression(max_iter=1000).fit(sc.transform(X(tr, fs)), [r["ok"] for r in tr])
            a_ = roc_auc_score([r["ok"] for r in te], clf.predict_proba(sc.transform(X(te, fs)))[:, 1])
            line.append(f"{name}={a_:.2f}")
            JSON["h12"].setdefault(m, {})[name] = float(a_)
        corr = np.corrcoef(X(rows, ["hedge", "length", "factor_consistency", "scenario_overlap"]).T)
        p(f"   {m:7s} held-out AUC: " + ", ".join(line))
        p(f"   {m:7s} correlations: hedge~length {corr[0,1]:.2f}, length~overlap {corr[1,3]:.2f}, hedge~consistency {corr[0,2]:.2f}, consistency~overlap {corr[2,3]:.2f}")
    p("")

    # accuracy gap for the supported features, as a practical effect size
    p("== Practical effect of the supported single-feature hypotheses (all five prompts and held-out scenarios, accuracy by feature) ==")
    for m in models:
        rows = [r for r in runs[m] if r["t"] in NT]
        h = [r["ok"] for r in rows if r["feat"]["hedge"] > 0]
        n_ = [r["ok"] for r in rows if r["feat"]["hedge"] == 0]
        p(f"   {m:7s} hedging in the why: accuracy {np.mean(h):.2f} (n={len(h)}) vs none {np.mean(n_):.2f} (n={len(n_)})")
        JSON.setdefault("hedge_accuracy", {})[m] = dict(hedged=float(np.mean(h)), n_hedged=len(h), not_hedged=float(np.mean(n_)), n_not=len(n_))
    p("\nSupported hypotheses:", supported if supported else "none")
    p(f"Hypotheses tried: {len(HYPS)} (a lucky pass is likely at this count; hence held-out + both models + CI).")
    JSON["supported"] = supported
    tag = Path(paths[0]).stem.split("_low_")[-1]
    outdir = Path(paths[0]).parent
    (outdir / f"rq1_why_analysis_{tag}.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")
    (outdir / f"rq1_why_analysis_{tag}.json").write_text(json.dumps(JSON, indent=1, default=float), encoding="utf-8")
    print(f"\nWrote {outdir / f'rq1_why_analysis_{tag}.txt'} and .json")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
