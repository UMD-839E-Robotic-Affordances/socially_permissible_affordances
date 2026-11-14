#!/usr/bin/env bash
# Opus 5.5 WITH web search (max 3 searches per call), then the analysis. Effort is medium by default;
# override with EFFORT=max etc. Costs more than the no-web run: searches are billed per search and
# results add input tokens (not yet measured; expect roughly $8-30 at medium).
# Usage: [EFFORT=high] [YES=1] rq1/scripts/run_opus_web.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
EFFORT="${EFFORT:-medium}"
confirm_cost "Opus 5.5, effort $EFFORT, WITH web search: 570 calls. Roughly \$8-30 at medium (unmeasured); more at higher effort."
run_and_analyze claude-opus-5-5 "$EFFORT" "-web" --web-search --max-searches 3 "$@"
