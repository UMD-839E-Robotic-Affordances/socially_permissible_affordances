#!/usr/bin/env bash
# Opus 5.5 (web search is off), then the analysis. Effort is medium by default; override with EFFORT=max etc.
# Asks a follow-up "why" after each judgment (--why; WHY=0 turns it off). Medium measured on a 5-scenario
# pilot without --why: about $5-6 for 570 calls; with --why (1,140 calls) expect roughly $8-10.
# Higher efforts cost more (thinking tokens are billed as output).
# Usage: [EFFORT=high] [WHY=0] [YES=1] rq1/scripts/run_opus.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
EFFORT="${EFFORT:-medium}"
confirm_cost "Opus 5.5, effort $EFFORT: 1,140 calls with --why. Roughly \$8-10 at medium (\$5-6 without --why); more at higher effort."
run_and_analyze claude-opus-5-5 "$EFFORT" "" $(why_args) "$@"
