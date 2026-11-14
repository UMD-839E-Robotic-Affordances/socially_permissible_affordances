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
    - `run_haiku.sh` — Haiku 5.5, effort low (about 570 calls, about 10 minutes, about $0.10).
    - `run_opus.sh` — Opus 5.5, effort medium by default (`EFFORT=max` etc. to change). About $5–6 (measured pilot); it asks for confirmation (`YES=1` skips it).
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
