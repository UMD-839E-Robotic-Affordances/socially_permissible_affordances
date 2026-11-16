# Socially Permissible Affordances

Research dataset and experiments on whether a consumer robot in a shared space should
accept, reject, or be uncertain about an action toward a goal.

- `dataset.json` — the final dataset: `dataset_review/scenarios.py` with the reviews in `dataset_review/reviewed.json` applied (regenerate with `python3 dataset_review/build_dataset.py`).
- `dataset_review/` — everything used to build and review the dataset:
  - `scenarios.py` — the scenario dataset (`SCENARIOS`, a list of `Scenario` tuples: context, goal, action, object, judgment, tags, summary).
  - `categories.json` — category taxonomy: groups (Physical / Coordination / Social), display labels and definitions.
  - `review.py` — local web UI to step through scenarios, edit fields, add notes,
  and ask Claude (via the `claude` CLI) to revise an entry.
  - `reviewed.json` — saved review progress and notes.
  - `build_dataset.py` — applies the reviews to the scenarios and writes `dataset.json`.
- `rq1/` — RQ1 experiment code:
  - `llm.py` — `LLMProvider`: one interface for Claude, OpenAI and a keyless `"mock"` provider. `call(query)` returns a validated `Judgment` (`accept` / `reject` / `uncertain`).
  - `model_configs.py` — `CONFIGS`: the valid model / thinking / effort combinations (found by probing the APIs).
  - `rq1_experiment.py` — runs every scenario under five prompt types (`none`, `taxonomy`, `examples`, `examples_nolabel` (examples with only the correct response), `tax+ex`) and writes `rq1/results/rq1_results_<model>_<effort>[_<tag>].json` (with the config, prompt lengths and answers); prints accuracy, balanced accuracy and macro-F1. Uses the mock by default. Options: `--model`, `--effort`, `--tag`, and `--web-search` / `--max-searches N` (Claude only; gives the model Anthropic's web search tool; off by default and not used in our runs: in a test the model never searched).
  - `analysis.py` — statistics on a results file (`python rq1/analysis.py <results.json>`).
  - `scripts/` — one-command runs that do the experiment and then the analysis; results files are tagged with the git hash:
    - `run_haiku.sh` — Haiku 5.5, effort low, with the follow-up `--why` question (about 1,140 calls, about 15 minutes, about $0.15; `WHY=0` turns it off).
    - `run_opus.sh` — Opus 5.5, effort medium by default (`EFFORT=max` etc. to change). With `--why` roughly $8–10 ($5–6 without; `WHY=0` turns it off); it asks for confirmation (`YES=1` skips it).
  - `analyze_why.py` — preliminary look at whether the kind of reason the model gives (theme and framing, hand-labeled in `dataset_with_whys.json`; see `rq1/WHY_THEMES.md`) goes with a correct judgment. It joins the labeled whys with a results file from a `--why` run.
  - `test_llm.py` — pytest tests.
- `setup.sh` — creates `.venv`, installs `requirements.txt`, checks API keys, runs the tests.

## Setup

```
./setup.sh
source .venv/bin/activate
```

API keys are read from the `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` environment variable, or else from
`~/.secrets/anthropic_api_key` / `~/.secrets/openai_api_key`. If a key file is missing, `setup.sh` asks you to
paste the key and saves it there with mode 600 (leave empty to skip). Never commit keys.

## Running

```
pytest rq1                          # offline; uses the mock when no key exists
RUN_LIVE_LLM=1 pytest rq1 -k live   # also calls the real models (costs money)
python rq1/rq1_experiment.py        # RQ1 experiment (mock provider by default)
```

`default_llm()` in `llm.py` picks OpenAI, then Anthropic, if a key exists; with neither it warns and uses the mock.

## Reviewing

```
cd dataset_review
python3 review.py [--out reviewed.json] [--port N]
```

Opens a local page (any free port unless `--port` is given). Each save is written
to `reviewed.json` (default); restarting resumes at the first unreviewed scenario.
Needs Python 3.10+ and, for the "Ask Claude" box, the `claude` CLI on your PATH.

The **Categories** tab shows every category with its definition (editable inline) and lets you ask Claude to merge, remove, rename or add categories; it edits `categories.json`, `scenarios.py` and the saved reviews, after saving a backup to `.backups/`.

After reviewing, rerun `python3 dataset_review/build_dataset.py` to refresh `dataset.json`.

## RQ1 design note: why we dropped the fixed few-shot examples

In the preliminary Haiku runs, the three fixed examples (S001, S003, S004, one per class) **did not improve prediction accuracy**, with or without the taxonomy. The taxonomy was the only context that helped. This is the evidence for the decision to stop using constant examples and to try a per-scenario relevant example instead (the `relevant_examples` branch), and to not spend more calls testing further variants of the fixed-example design.

**Data.** Two repeats of the same five prompt types, claude-haiku-5-5, effort low, 114 scenarios each. They are in `rq1/results/deprecated/` (kept there until the remaining scenarios are reviewed):
`rq1_results_claude-haiku-5-5_low_877e10d.json` (run A) and `rq1_results_claude-haiku-5-5_low_pr1-adc09bf.json` (run B). Statistics are from `rq1/analysis.py`: an exact McNemar test on paired correctness (fixed / broke = scenarios the prompt made right / wrong compared with the baseline) and a 95% bootstrap CI that resamples scenarios.

| Prompt | Accuracy A | Accuracy B | Balanced acc A | Balanced acc B |
|---|---|---|---|---|
| none | 0.789 | 0.789 | 0.590 | 0.590 |
| taxonomy | 0.851 | 0.851 | 0.663 | 0.663 |
| examples (3 fixed, with reasoning) | 0.781 | 0.789 | 0.653 | 0.623 |
| examples_nolabel (3 fixed, response only) | 0.772 | 0.754 | 0.576 | 0.595 |
| tax+ex (taxonomy + 3 fixed examples) | 0.842 | 0.851 | 0.672 | 0.696 |

Always answering "reject" scores 0.781.

| Comparison | Run A: change, fixed/broke, p | Run B: change, fixed/broke, p | Both runs: fixed / broke |
|---|---|---|---|
| examples vs none | -0.009, 6/7, p=1.00 | 0.000, 4/4, p=1.00 | 10 / 11 |
| examples_nolabel vs none | -0.018, 3/5, p=0.73 | -0.035, 4/8, p=0.39 | 7 / 13 |
| tax+ex vs taxonomy (value of examples on top of the taxonomy) | -0.009, 2/3, p=1.00 | 0.000, 3/3, p=1.00 | 5 / 6 |
| taxonomy vs none (for contrast) | +0.061, 9/2, p=0.065 | +0.061, 9/2, p=0.065 | 18 / 4 |

- Adding the fixed examples changed accuracy by -3.5 to 0.0 points. The CIs for the accuracy change are about [-0.07, +0.05] (examples) and [-0.05, +0.04] (tax+ex vs taxonomy), so they include no change. Across both runs the examples fixed 10 and broke 11 scenarios, and on top of the taxonomy fixed 5 and broke 6.
- Balanced accuracy was slightly higher with the examples in some cells (up to +0.06), but every CI includes zero (for example [-0.06, +0.19] for examples vs none in run A).
- The same prompts gave the same answer 96-97% of the time across the two runs, so differences of one or two points are within run-to-run noise.
- The earlier runs agree: the first run (old prompts, 117 scenarios, results in `rq1_results_claude-haiku-5-5_low.json`) had taxonomy 0.872 vs taxonomy + examples 0.863 (2 fixed, 3 broke, p=1.0), and run `..._pr1-54cc47f.json` had examples 0.728 vs none 0.772 (5 fixed, 10 broke, p=0.30).

**Decision.** The fixed examples gave no measurable benefit, so we do not run more conditions on that design (a random-example control, different example counts, or other selections): every extra condition adds about 114 calls per model and prompt type, and more with several seeds or a larger model, and these runs already explain the choice.

**Limits.** One model (Haiku 5.5, effort low), 114 scenarios, and 11 accept / 14 uncertain scenarios. With CIs of about +/-5 points, a benefit larger than about 5 points is unlikely, but a small one cannot be ruled out. The three fixed examples were hand-picked and all concern ownership and permission. Only 59 of 119 scenarios are reviewed, so these results are preliminary.
