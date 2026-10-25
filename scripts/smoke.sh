#!/bin/bash
# Read-only check of the RUNNING app (default http://localhost:8100): is everything answering?
#   scripts/smoke.sh [base-url]
BASE="${1:-http://localhost:8100}"; FAIL=0
check() {  # name, path, expected substring
  out=$(curl -s -m 8 "$BASE$2"); code=$?
  if [ $code -eq 0 ] && [[ "$out" == *"$3"* ]]; then echo "ok   $1"; else echo "FAIL $1 ($2)"; FAIL=1; fi
}
check "API status"   /api/status    '"model"'
check "Settings"     /api/settings  '"default_persona"'
check "Catalog"      /api/catalog   '"modalities"'
check "Sessions"     /api/sessions  '['
check "UI is served" /              '<div id="root">'
exit $FAIL
