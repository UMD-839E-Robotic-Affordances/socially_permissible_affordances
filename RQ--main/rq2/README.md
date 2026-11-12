# RQ2: add-only vs rule-refactoring (preliminary prototype)

This directory is independent of the COMS team RQ1 implementation and does not modify any team files.

## Organization
- `src/rq2.py`: scenario loading, Groq JSON API/cache, predicate grounding, deterministic rule evaluator, B1/B2 update validation, feedback experiment, metrics and plots.
- `tests/`: dataset, grounding parser and rule-operation tests.
- `data/`: snapshots of the team dataset (120 scenarios) and working taxonomy.
- `notebooks/RQ2_Colab.ipynb`: runner using Colab Secrets.

## Run
Install `pip install -r rq2/requirements.txt`, then run:

```bash
python -m unittest discover -s rq2/tests -v
python rq2/src/rq2.py --data rq2/data/current_dataset.json --output rq2/local_outputs --max-scenarios 20 --max-steps 8 --seeds 17
```

Set `GROQ_API_KEY` in the environment, never in the repository. The API cache and experiment outputs are excluded from source control.

## Scientific status
This is preliminary research code, not validated RQ2 evidence. The initial pilot suffered a grounding-response parsing bug; reconstructed metrics are exploratory. The rule interpreter uses last-match-wins precedence and the validator is primarily syntactic. B2 did not exercise structural revision in the original pilot. Do not claim superiority of refactoring.

## Provenance
Prepared from the locally audited `RQ2_GITHUB_ADD_ONLY.zip` package. Nine offline tests passed prior to upload.
