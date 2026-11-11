# Socially Permissible Affordances

- `dataset.json` — the final dataset: `scenarios.py` with the reviews in `dataset_review/reviewed.json` applied (regenerate with `python3 dataset_review/build_dataset.py`).
- `dataset_review/` — everything used to build and review the dataset:
  - `scenarios.py` — the scenario dataset (`SCENARIOS`, a list of `Scenario` tuples: context, goal, action, object, judgment, tags, summary).
  - `categories.json` — category taxonomy: groups (Physical / Coordination / Social), display labels and definitions.
  - `review.py` — local web UI to step through scenarios, edit fields, add notes,
  and ask Claude (via the `claude` CLI) to revise an entry.

## Reviewing

```
cd dataset_review
python3 review.py [--out reviewed.json] [--port N]
```

Opens a local page (any free port unless `--port` is given). Each save is written
to `reviewed.json` (default); restarting resumes at the first unreviewed scenario.
Needs Python 3.10+ and, for the "Ask Claude" box, the `claude` CLI on your PATH.

The **Categories** tab shows every category with its definition (editable inline) and lets you ask Claude to merge, remove, rename or add categories; it edits `categories.json`, `scenarios.py` and the saved reviews, after saving a backup to `.backups/`.
