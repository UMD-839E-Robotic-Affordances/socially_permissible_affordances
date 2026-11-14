#!/usr/bin/env bash
# Haiku 5.5, effort low, all five prompt types, then the analysis.
# About 570 calls and 10 minutes; roughly $0.10 (see the README for the token math).
# Usage: rq1/scripts/run_haiku.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
run_and_analyze claude-haiku-5-5 low "" "$@"
