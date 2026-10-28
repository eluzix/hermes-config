#!/usr/bin/env bash
set -euo pipefail

shopt -s nullglob
browsers=("$HOME"/.agent-browser/browsers/chrome-*/chrome)
if (( ${#browsers[@]} == 0 )); then
  echo "No agent-browser Chromium installation found" >&2
  exit 1
fi

chrome="${browsers[${#browsers[@]} - 1]}"
hermes_home="${HERMES_HOME:-$HOME/.hermes}"

exec "$chrome" \
  --headless=new \
  --remote-debugging-address=127.0.0.1 \
  --remote-debugging-port=9223 \
  --user-data-dir="$hermes_home/browser-profile/headless-automation" \
  --no-first-run \
  --no-default-browser-check \
  --disable-background-networking \
  --disable-component-update \
  --disable-sync \
  --disable-dev-shm-usage \
  about:blank
