#!/bin/sh
# Writes `/config.json` from the [Runtime](/architecture/services/frontend.md#runtime) keys the
# client reads, so the client can pick them up without a rebuild. Runs before nginx starts, as
# every script in `/docker-entrypoint.d/` of the base image does.
set -eu

RUN_POLL_INTERVAL_MS="${RUN_POLL_INTERVAL_MS:-2000}"
ALERT_POLL_INTERVAL_MS="${ALERT_POLL_INTERVAL_MS:-60000}"
CONFIDENCE_HIGH_MIN="${CONFIDENCE_HIGH_MIN:-0.85}"
CONFIDENCE_MEDIUM_MIN="${CONFIDENCE_MEDIUM_MIN:-0.65}"
export RUN_POLL_INTERVAL_MS ALERT_POLL_INTERVAL_MS CONFIDENCE_HIGH_MIN CONFIDENCE_MEDIUM_MIN

envsubst '${RUN_POLL_INTERVAL_MS} ${ALERT_POLL_INTERVAL_MS} ${CONFIDENCE_HIGH_MIN} ${CONFIDENCE_MEDIUM_MIN}' \
  < /usr/share/nginx/html/config.json.template \
  > /usr/share/nginx/html/config.json
