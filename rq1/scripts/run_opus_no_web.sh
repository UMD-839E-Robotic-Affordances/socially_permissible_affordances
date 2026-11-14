#!/usr/bin/env bash
# Opus 5.5, effort max, WITHOUT web search, then the analysis.
# Expensive: roughly $15-65 for a full run (input ~$4, thinking tokens are billed as output).
# Usage: rq1/scripts/run_opus_no_web.sh [extra rq1_experiment.py args]   (YES=1 skips the prompt)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
confirm_cost "Opus 5.5 at max effort, no web search: 570 calls, roughly \$15-65."
run_and_analyze claude-opus-5-5 max "-noweb" "$@"
