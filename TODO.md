# TODO

Dataset (files are in `dataset_review/`; rerun `python3 dataset_review/build_dataset.py` afterwards to refresh `dataset.json`):

- [ ] Review S102 (questionable scenario; left unreviewed on purpose, see the comment in `scenarios.py`).
- [ ] Finish reviewing the remaining scenarios (59 of 119 reviewed so far).

RQ1 experiment:

- [ ] Run the experiment with real models from `rq1/model_configs.py` instead of the mock (360 calls per model), and save results per model.
- [ ] Support Sonnet 5.5's `between_tools` thinking mode in `LLMProvider` (`thinking` is currently a boolean).

Done:

- [x] Add all member examples to GitHub (repo exists and is pushed).
