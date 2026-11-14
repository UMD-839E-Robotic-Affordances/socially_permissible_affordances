#!/usr/bin/env bash
# Haiku 5.5, effort low, all five prompt types, then the analysis.
# Asks a follow-up "why" after each judgment (--why; WHY=0 turns it off). About 1,140 calls, roughly
# 15 minutes and $0.15 (without --why: 570 calls, 10 minutes, $0.10).
# Usage: rq1/scripts/run_haiku.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
run_and_analyze claude-haiku-5-5 low "" $(why_args) "$@"
