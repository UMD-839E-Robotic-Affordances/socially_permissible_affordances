"""Copy authoritative RQ2 dataset/taxonomy snapshots from the team repo ZIP.

Usage:
    python rq2/data/import_from_team_zip.py /path/to/socially_permissible_affordances-main.zip

Never publish a private team dataset in a public repository. This utility writes
only two new files within rq2/data/ and refuses to overwrite either file.
"""
from pathlib import Path
import json
import sys
import zipfile

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python rq2/data/import_from_team_zip.py /path/to/team-repo.zip")
    archive = Path(sys.argv[1])
    outdir = Path(__file__).resolve().parent
    targets = {
        "dataset.json": "current_dataset.json",
        "dataset_review/categories.json": "current_categories.json",
    }
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        for suffix, dest_name in targets.items():
            candidates = [n for n in names if n.endswith("/" + suffix)]
            if len(candidates) != 1:
                raise RuntimeError(f"Expected exactly one {suffix}, found {len(candidates)}")
            destination = outdir / dest_name
            if destination.exists():
                raise FileExistsError(f"Refusing to overwrite {destination}")
            raw = z.read(candidates[0])
            json.loads(raw.decode("utf-8"))  # Validate JSON before writing
            destination.write_bytes(raw)
            print(f"Copied {candidates[0]} -> {destination}")
if __name__ == "__main__":
    main()
