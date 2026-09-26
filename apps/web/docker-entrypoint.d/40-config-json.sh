#!/bin/sh
# Run by the nginx image's entrypoint before nginx starts: writes /config.json for the client
# (frontend Design). Under `set -eu` a missing key stops the container.
set -eu

/usr/local/bin/config-json.sh > /usr/share/nginx/html/config.json
