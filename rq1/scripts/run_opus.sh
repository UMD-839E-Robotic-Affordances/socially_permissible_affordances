#!/usr/bin/env bash
# Opus 5.5 (web search is off), then the analysis. NOTE: Sonnet 5.5 costs half as much per token; run_all.sh uses it instead. Effort is medium by default; override with EFFORT=max etc.
# Asks a follow-up "why" after each judgment (--why; WHY=0 turns it off). Medium measured on a 5-scenario
# pilot without --why; for the current 143 scenarios with --why (1,430 calls) expect roughly $10-14 at medium, less at low.
# Higher efforts cost more (thinking tokens are billed as output).
# Usage: [EFFORT=high] [WHY=0] [YES=1] rq1/scripts/run_opus.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
EFFORT="${EFFORT:-medium}"
confirm_cost "Opus 5.5, effort $EFFORT: 1,430 calls with --why. Roughly \$10-14 at medium, less at low; more at higher effort."
run_and_analyze claude-opus-5-5 "$EFFORT" "" $(why_args) $(structured_args) "$@"
