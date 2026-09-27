#!/bin/sh
# Prints the body of /config.json from the environment: the keys of frontend Runtime that reach the
# client at run time. A missing key fails naming it; there is no default (P-10).
set -eu

: "${CONFIDENCE_HIGH_MIN:?CONFIDENCE_HIGH_MIN is not set}"
: "${CONFIDENCE_MEDIUM_MIN:?CONFIDENCE_MEDIUM_MIN is not set}"
: "${RUN_POLL_INTERVAL_MS:?RUN_POLL_INTERVAL_MS is not set}"
: "${DEMO_SIGN_IN:?DEMO_SIGN_IN is not set}"

printf '{"CONFIDENCE_HIGH_MIN": "%s", "CONFIDENCE_MEDIUM_MIN": "%s", "RUN_POLL_INTERVAL_MS": "%s", "DEMO_SIGN_IN": "%s"}\n' \
  "$CONFIDENCE_HIGH_MIN" "$CONFIDENCE_MEDIUM_MIN" "$RUN_POLL_INTERVAL_MS" "$DEMO_SIGN_IN"
