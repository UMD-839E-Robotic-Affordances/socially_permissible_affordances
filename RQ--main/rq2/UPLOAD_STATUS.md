# Upload status and data provenance

The RQ2 source code, offline unit tests, and Colab notebook were committed to this separate private repository without deleting or overwriting any pre-existing file.

The two authoritative snapshots (`rq2/data/current_dataset.json` and `rq2/data/current_categories.json`) are **not committed** here. The team repository is private, and its original data should remain under the team's access controls rather than being duplicated into a personal repository without team approval.

To run independently from an authorized local copy of the team repository ZIP:

```bash
python rq2/data/import_from_team_zip.py /path/to/socially_permissible_affordances-main.zip
python -m pip install -r rq2/requirements.txt
python -m unittest discover -s rq2/tests -v
```

The import script refuses to overwrite existing snapshots. The original source archive is the authoritative dataset; the team working taxonomy is not finalized. No private API key, raw API cache, or invalid pilot output has been committed.

Scientific caution: The original pilot suffered a grounding-parser failure. Cache-only reconstructed metrics are exploratory, not valid proof that rule refactoring improves accuracy. A full corrected API experiment is not documented as completed here.
