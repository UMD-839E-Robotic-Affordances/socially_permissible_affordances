#!/usr/bin/env bash
# Haiku 5.5, effort low, all five prompt types, then the analysis.
# Asks a follow-up "why" after each judgment (--why; WHY=0 turns it off): 143 scenarios x 5 prompts x 2 calls
# = about 1,430 calls, roughly 30 minutes and $0.30 (projected from a 5-scenario sample). The whys are saved in a separate
# rq1_whys_*.json file. The answer is constrained to a JSON schema (--structured; STRUCTURED=0 turns it off).
# The results file is rewritten after every scenario. To resume an interrupted run, add
# "--tag <same tag> --start-index <N>" (the experiment prints N when it stops).
# Usage: rq1/scripts/run_haiku.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
run_and_analyze claude-haiku-5-5 low "" $(why_args) $(structured_args) "$@"
