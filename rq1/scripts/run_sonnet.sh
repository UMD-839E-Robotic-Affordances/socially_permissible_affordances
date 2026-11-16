#!/usr/bin/env bash
# Sonnet 5.5, effort low (default; EFFORT=medium etc. overrides), all five prompt types, then the analysis.
# Sonnet costs half as much per token as Opus ($2/$10 vs $4/$20 per million tokens), so this replaces Opus in run_all.sh.
# With --why (on by default; WHY=0 turns it off): about 1,430 calls, roughly 45 minutes and $4-6 (estimate, not measured).
# Resume an interrupted run with "--tag <same tag> --start-index <N>".
# Usage: [EFFORT=medium] [WHY=0] rq1/scripts/run_sonnet.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
EFFORT="${EFFORT:-low}"
run_and_analyze claude-sonnet-5-5 "$EFFORT" "" $(why_args) "$@"
