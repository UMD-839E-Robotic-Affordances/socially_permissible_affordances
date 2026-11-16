# TODO

Dataset (files are in `dataset_review/`; rerun `python3 dataset_review/build_dataset.py` afterwards to refresh `dataset.json`):

- [x] Review all scenarios (141 of 141 reviewed; accept/reject counterparts added so most tags have both polarities).
- [ ] Add an accept scenario for the `cost` and `environmental` tags (the only tags without one).
- [ ] Optional wording cleanup: actions that end mid-phrase and rely on the object field (S011, S014, S023, S024, S117).
- [ ] Optional: 76 of 141 scenarios have no `summary`, so the `examples` prompts show no reasoning for them.

RQ1 experiment:

- [ ] Re-run the experiment on the final dataset: the results in `rq1/results/deprecated/` and `dataset_with_whys.json` were produced on the dataset before the review was finished (114 scored scenarios; now 141, 705 calls per model without `--why`).
- [ ] Optional: exclude scenarios with an identical context from the example selection (about 2 of 141 draw one per run, always with the opposite label).
- [ ] Run the experiment with real models from `rq1/model_configs.py` and save results per model.
- [ ] Support Sonnet 5.5's `between_tools` thinking mode in `LLMProvider` (`thinking` is currently a boolean).

Done:

- [x] Add all member examples to GitHub (repo exists and is pushed).
