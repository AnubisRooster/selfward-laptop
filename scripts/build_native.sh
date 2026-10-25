#!/bin/bash
# Builds Selfward's own window (the Tauri shell) and puts the binary where the launcher expects it.
# The interface inside it is the web app the API serves, so after a front-end change you only need
# scripts/build_ui.sh; rebuild the shell only when frontend/src-tauri changes.
set -e
cd "$(dirname "$0")/../frontend"
. "$HOME/.cargo/env"
[ -d node_modules ] || npm ci
npm run tauri build -- --no-bundle
mkdir -p ../resources/selfward-ui-bin
cp src-tauri/target/release/selfward ../resources/selfward-ui-bin/selfward
echo "Built $(cd .. && pwd)/resources/selfward-ui-bin/selfward"
