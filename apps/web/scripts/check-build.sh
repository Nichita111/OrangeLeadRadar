#!/bin/sh
# Builds for production with the development mock's password set to a marker, then fails if the
# build output contains the mock: its worker script, its log prefix or the marker (G15).
set -eu

marker="dev-mock-marker-$$"
rm -rf dist
VITE_DEV_MOCK_PASSWORD="$marker" npm run build

if grep -rIl -e "mockServiceWorker" -e "\[MSW\]" -e "$marker" dist; then
  echo "check:build: the production build contains the development mock." >&2
  exit 1
fi
echo "check:build: the production build holds no development mock."

# FR-109: no font or icon comes from a URL; the build references none in its markup or styles.
if grep -E -e '<(link|script)[^>]*(href|src)="https?://' dist/index.html \
  || grep -r -E -e 'url\(["'"'"']?https?://' --include='*.css' dist; then
  echo "check:build: the production build references an external font, icon or script." >&2
  exit 1
fi
echo "check:build: the production build references no external URL."
