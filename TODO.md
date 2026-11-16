# TODO

Dataset (files are in `dataset_review/`; rerun `python3 dataset_review/build_dataset.py` afterwards to refresh `dataset.json`):

- [x] Review all scenarios (143 of 143 reviewed; accept/reject counterparts added so every tag has both an accept and a reject).
- [ ] Optional wording cleanup: actions that end mid-phrase and rely on the object field (S011, S014, S023, S024, S117).
- [ ] Optional: about half of the scenarios have no `summary`, so the `examples` prompts show no reasoning for them.

RQ1 experiment:

- [ ] Re-run the experiment on the final dataset: the results in `rq1/results/deprecated/` and `dataset_with_whys.json` were produced on the dataset before the review was finished (114 scored scenarios; now 143, 715 calls per model without `--why`).
- [ ] Optional: exclude scenarios with an identical context from the example selection (about 2 of 143 draw one per run, always with the opposite label).
- [ ] Run `rq1/scripts/run_all.sh` (Haiku 5.5 low, then Sonnet 5.5 low) on the final dataset; the results files are rewritten after every scenario and can be resumed with `--start-index`.
- [ ] Run other models from `rq1/model_configs.py` and save results per model.
- [ ] Support Sonnet 5.5's `between_tools` thinking mode in `LLMProvider` (`thinking` is currently a boolean).

Done:

- [x] Add all member examples to GitHub (repo exists and is pushed).
