#!/bin/sh
set -eu
# Adapter supplies the trusted simulator state and verifier output directory.
: "${PILOT_STATE:?Set PILOT_STATE to simulator-owned state.json}"
python3 "$(dirname "$0")/verify.py" "$PILOT_STATE" --output "${VERIFIER_OUTPUT:-/logs/verifier}"
