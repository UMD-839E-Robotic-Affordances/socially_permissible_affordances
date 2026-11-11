"""Build ../dataset.json: scenarios.py with the saved reviews (reviewed.json) applied.

Run:  python3 dataset_review/build_dataset.py
Reviewed fields override the scenario's; review metadata (notes, changed, reviewed_at) is dropped.
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenarios

FIELDS = ("id", "context", "goal", "action", "object", "judgment", "tags", "summary")

reviews = json.loads((HERE / "reviewed.json").read_text(encoding="utf-8"))
out = []
for s in scenarios.SCENARIOS:
    rec = {**s._asdict(), **{k: v for k, v in reviews.get(s.id, {}).items() if k in FIELDS}}
    rec["tags"] = list(rec["tags"])
    rec["reviewed"] = s.id in reviews
    out.append({k: rec.get(k) for k in (*FIELDS, "reviewed")})

path = HERE.parent / "dataset.json"
path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Wrote {len(out)} scenarios ({sum(r['reviewed'] for r in out)} reviewed) to {path}")
