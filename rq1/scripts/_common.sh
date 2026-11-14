# Shared helper, sourced by the run_*.sh scripts (not run directly).
# run_and_analyze MODEL EFFORT TAG_SUFFIX [extra experiment args...]
#   1. runs rq1/rq1_experiment.py on every scenario and prompt type
#   2. runs rq1/analysis.py on the results file it wrote
# The results file is named rq1_results_<model>_<effort>_<git hash><suffix>.json.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

confirm_cost() {  # confirm_cost "message"; skipped with YES=1 or when not run from a terminal
  echo "$1"
  if [ "${YES:-}" != "1" ] && [ -t 0 ]; then
    read -r -p "Continue? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }
  fi
}

run_and_analyze() {
  local model="$1" effort="$2" suffix="$3"; shift 3
  local hash; hash="$(git -C "$ROOT" rev-parse --short HEAD)"
  [ -z "$(git -C "$ROOT" status --porcelain -- rq1 dataset.json dataset_review)" ] || \
    echo "WARNING: uncommitted changes; the hash $hash does not describe the code being run."
  local out; out="$(mktemp)"
  echo "== Experiment: model=$model effort=$effort tag=${hash}${suffix} =="
  "$PY" "$ROOT/rq1/rq1_experiment.py" --model "$model" --effort "$effort" --tag "${hash}${suffix}" "$@" | tee "$out"
  local results; results="$(grep -a '^Results saved to ' "$out" | tail -1 | sed 's/^Results saved to //')"
  rm -f "$out"
  [ -n "$results" ] || { echo "Could not find the results file in the experiment output."; exit 1; }
  echo
  echo "== Analysis: $results =="
  "$PY" "$ROOT/rq1/analysis.py" "$results"
}
