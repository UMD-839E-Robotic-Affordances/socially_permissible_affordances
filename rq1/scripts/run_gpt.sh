#!/usr/bin/env bash
# GPT-6 Luna (OpenAI's cheapest GPT-6 tier, about $0.10 / $0.50 per million input / output tokens, third-party figures),
# effort low, all five prompt types, then the analysis. Same settings as run_haiku.sh and run_sonnet.sh: the answer is
# constrained to the JSON object {"judgment": ...} (--structured; STRUCTURED=0 turns it off) and the follow-up why is asked
# in the same conversation (WHY=0 turns it off). Needs ~/.secrets/openai_api_key or OPENAI_API_KEY.
# About 1,430 calls; the cost forecast is in the README (measured on a small sample; hidden reasoning tokens count as output).
# Resume an interrupted run with "--tag <same tag> --start-index <N>".
# Usage: [MODEL=gpt-6-luna] [EFFORT=low] [WHY=0] rq1/scripts/run_gpt.sh [extra rq1_experiment.py args]
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
MODEL="${MODEL:-gpt-6-luna}"
EFFORT="${EFFORT:-low}"
run_and_analyze "$MODEL" "$EFFORT" "" $(why_args) $(structured_args) "$@"
