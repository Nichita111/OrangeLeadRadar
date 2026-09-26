#!/bin/sh
# Prints the body of /config.json from the environment: the keys of frontend Runtime that reach the
# client at run time. A missing key fails naming it; there is no default (P-10).
set -eu

: "${CONFIDENCE_HIGH_MIN:?CONFIDENCE_HIGH_MIN is not set}"
: "${CONFIDENCE_MEDIUM_MIN:?CONFIDENCE_MEDIUM_MIN is not set}"

printf '{"CONFIDENCE_HIGH_MIN": "%s", "CONFIDENCE_MEDIUM_MIN": "%s"}\n' \
  "$CONFIDENCE_HIGH_MIN" "$CONFIDENCE_MEDIUM_MIN"
