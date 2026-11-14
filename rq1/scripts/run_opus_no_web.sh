#!/usr/bin/env bash
# Opus 5.5 WITHOUT web search, then the analysis. Effort is medium by default; override with EFFORT=max etc.
# Medium measured on a 5-scenario pilot: about $5-6 for the full 570 calls. Higher efforts cost more
# (thinking tokens are billed as output).
# Usage: [EFFORT=high] [YES=1] rq1/scripts/run_opus_no_web.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
EFFORT="${EFFORT:-medium}"
confirm_cost "Opus 5.5, effort $EFFORT, no web search: 570 calls. About \$5-6 at medium (measured pilot); more at higher effort."
run_and_analyze claude-opus-5-5 "$EFFORT" "-noweb" "$@"
