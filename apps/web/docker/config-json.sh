#!/bin/sh
# Prints `/config.json` from the environment, with the defaults of
# [Runtime](/architecture/services/frontend.md#runtime) — the one place these defaults live.
# The `web` container's entrypoint hook writes this to the html root; the Vite dev server runs
# it to answer the same path ([frontend Design](/architecture/services/frontend.md#design)).
set -eu

cat <<JSON
{
  "RUN_POLL_INTERVAL_MS": ${RUN_POLL_INTERVAL_MS:-2000},
  "ALERT_POLL_INTERVAL_MS": ${ALERT_POLL_INTERVAL_MS:-60000},
  "CONFIDENCE_HIGH_MIN": ${CONFIDENCE_HIGH_MIN:-0.85},
  "CONFIDENCE_MEDIUM_MIN": ${CONFIDENCE_MEDIUM_MIN:-0.65},
  "MOCK_API": ${MOCK_API:-false}
}
JSON
