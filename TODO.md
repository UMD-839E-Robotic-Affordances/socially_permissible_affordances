# TODO

Dataset (files are in `dataset_review/`; rerun `python3 dataset_review/build_dataset.py` afterwards to refresh `dataset.json`):

- [ ] Remove the `consent` category ("consent / permission", Social group) from `dataset_review/categories.json`.
  - Remove the `consent` tag from every scenario in `dataset_review/scenarios.py` and from every `tags` list in `dataset_review/reviewed.json`.
  - Check whether any other category definition mentions permission or consent (`privacy` does) and reword it.
- [ ] Remove the `infeasible` category (Physical group, "The action cannot physically be carried out as described") from `dataset_review/categories.json`.
  - Remove the `infeasible` tag from `scenarios.py` and `reviewed.json`.
  - S048 has `infeasible` as its only tag, so give it a replacement tag.
- [ ] Finish reviewing the remaining scenarios (about 36 of 120 reviewed so far).

RQ1 experiment:

- [ ] Write the `examples` text in `rq1/rq1_experiment.py` (it is empty, so the `examples` prompt currently equals the `taxonomy` prompt plus a heading).
- [ ] Run the experiment with real models from `rq1/model_configs.py` instead of the mock (360 calls per model), and save results per model.
- [ ] Support Sonnet 5.5's `between_tools` thinking mode in `LLMProvider` (`thinking` is currently a boolean).

Done:

- [x] Add all member examples to GitHub (repo exists and is pushed).
