# TODO

Dataset (files are in `dataset_review/`; rerun `python3 dataset_review/build_dataset.py` afterwards to refresh `dataset.json`):

- [ ] Finish reviewing the remaining scenarios (36 of 117 reviewed so far).

RQ1 experiment:

- [ ] Write the `examples` text in `rq1/rq1_experiment.py` (it is empty, so the `examples` prompt currently equals the `taxonomy` prompt plus a heading).
- [ ] Run the experiment with real models from `rq1/model_configs.py` instead of the mock (360 calls per model), and save results per model.
- [ ] Support Sonnet 5.5's `between_tools` thinking mode in `LLMProvider` (`thinking` is currently a boolean).

Done:

- [x] Add all member examples to GitHub (repo exists and is pushed).
