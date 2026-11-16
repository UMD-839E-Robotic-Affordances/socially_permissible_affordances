#!/usr/bin/env bash
# Runs the whole RQ1 experiment on the final dataset: Haiku 5.5 (low), then Sonnet 5.5 (low), each followed by the
# analysis. Prints when each model starts and finishes, how long it took, and where the results are.
#
#   rq1/scripts/run_all.sh [extra rq1_experiment.py args, applied to both models]
#
# Each run saves its results file after every scenario (rq1/results/rq1_results_<model>_<effort>_<git hash>.json) and
# its follow-up "why" answers in a separate rq1_whys_*.json file next to it. If a run stops, the other model still
# runs, and the summary at the end says which one to resume. To resume one model, run its own script with
#   --tag <hash> --start-index <N>      e.g.  rq1/scripts/run_haiku.sh --tag 1a2b3c4 --start-index 59
# One seed (42) is used. Estimated total: about 1,430 calls per model, roughly 1.5 hours and $5-7.
# Run it from a clean, committed branch, ideally inside tmux or nohup (it takes over an hour).
set -uo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
EXTRA=("$@")
HASH="$(git -C "$ROOT" rev-parse --short HEAD)"
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
declare -a SUMMARY=()
FAILED=0

run_one() {  # run_one LABEL MODEL EFFORT
  local label="$1" model="$2" effort="$3" t0 t1 mins file
  t0=$(date +%s)
  echo
  echo "################ [$(stamp)] STARTED: $label ($model, effort $effort) ################"
  if ( set -e; run_and_analyze "$model" "$effort" "" $(why_args) "${EXTRA[@]+"${EXTRA[@]}"}" ); then
    t1=$(date +%s); mins=$(( (t1 - t0) / 60 )); file="rq1/results/rq1_results_${model}_${effort}_${HASH}.json"
    echo "################ [$(stamp)] DONE: $label in ${mins} min ################"
    SUMMARY+=("DONE   $label (${mins} min)  results: $file  whys: ${file/rq1_results_/rq1_whys_}")
  else
    t1=$(date +%s); mins=$(( (t1 - t0) / 60 )); FAILED=1
    echo "################ [$(stamp)] STOPPED: $label after ${mins} min (partial results are saved) ################"
    SUMMARY+=("STOPPED $label after ${mins} min: resume with its script and  --tag ${HASH} --start-index <N>")
  fi
}

echo "[$(stamp)] RQ1 run_all on commit $HASH: Haiku 5.5 (low), then Sonnet 5.5 (low); about 1,430 calls each."
[ -z "$(git -C "$ROOT" status --porcelain -- rq1 dataset.json dataset_review)" ] || \
  echo "WARNING: uncommitted changes; the hash $HASH does not describe the code being run."
T_ALL=$(date +%s)
run_one "Haiku 5.5" claude-haiku-5-5 low
run_one "Sonnet 5.5" claude-sonnet-5-5 low
echo
echo "================ [$(stamp)] ALL FINISHED in $(( ($(date +%s) - T_ALL) / 60 )) min ================"
for line in "${SUMMARY[@]}"; do echo "$line"; done
exit $FAILED
