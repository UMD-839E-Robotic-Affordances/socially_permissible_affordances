#!/usr/bin/env bash
# Opus 5.5, effort max, WITH web search (max 3 searches per call), then the analysis.
# Costs more than the no-web run: searches are billed per search and results add input tokens (roughly $25-115 in total).
# Usage: rq1/scripts/run_opus_web.sh [extra rq1_experiment.py args]   (YES=1 skips the prompt)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
confirm_cost "Opus 5.5 at max effort WITH web search: 570 calls, roughly \$25-115 including search fees."
run_and_analyze claude-opus-5-5 max "-web" --web-search --max-searches 3 "$@"
