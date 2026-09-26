#!/bin/sh
# Runs at container start, before nginx (the official image's `/docker-entrypoint.d/`
# convention): writes `/config.json` into the html root from `config-json.sh`, the one script
# that holds the [Runtime](/architecture/services/frontend.md#runtime) defaults.
set -eu

/docker/config-json.sh > /usr/share/nginx/html/config.json
