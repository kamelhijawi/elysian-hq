#!/bin/zsh
# Smoke-drive the Moon Shelter reports page (tools/report-server.py) with curl + headless Chrome.
# Read-only: it never POSTs /run/<job> (that would start a department bot on Claude headless).
# Usage, from hq/:  .claude/skills/run-hq/smoke.sh [--pdf]
#   --pdf   also hit /pdf for the newest sales file (writes moonshelter/live/pdf/sales-pulse.pdf; Chrome, ~5 s)
set -u
BASE=http://127.0.0.1:8770
OUT=${OUT:-${TMPDIR:-/tmp}/run-hq}; mkdir -p "$OUT"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fail(){ echo "FAIL: $*" >&2; exit 1 }
ok(){ echo "ok   $*" }

# 1. server up? (launchd keeps it alive as com.elysian.svc.reports; fall back to a direct start)
if ! curl -sf -o /dev/null "$BASE/status"; then
  launchctl kickstart "gui/$(id -u)/com.elysian.svc.reports" 2>/dev/null \
    || { nohup python3 "$(dirname "$0")/../../../tools/report-server.py" >>"$OUT/server.log" 2>&1 & }
  for i in {1..20}; do curl -sf -o /dev/null "$BASE/status" && break; sleep 0.5; done
  curl -sf -o /dev/null "$BASE/status" || fail "server did not come up on $BASE (see $OUT/server.log and ~/Library/Logs/elysian-svc-reports.log)"
fi
ok "server answers on $BASE"

# 2. home page: one card per registered department, each with a Generate button
curl -sf "$BASE/" >"$OUT/home.html" || fail "GET / failed"
grep -q 'Generate crm report' "$OUT/home.html" || fail "home page has no CRM card"
ok "home page renders $(grep -o 'data-job="[a-z]*"' "$OUT/home.html" | tr '\n' ' ')"

# 3. /status: JSON {job: [state, text]}
curl -sf "$BASE/status" >"$OUT/status.json" || fail "GET /status failed"
python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); [print("     ",k,s[k]) for k in s]' "$OUT/status.json" || fail "/status is not JSON"
ok "/status"

# 4. open the newest report of every job (the first /report link in each card)
for k in $(grep -o 'data-job="[a-z]*"' "$OUT/home.html" | cut -d'"' -f2); do
  href=$(grep -o "/report?job=$k&f=[^\"]*" "$OUT/home.html" | head -1)
  [ -z "$href" ] && { echo "     $k: no reports yet"; continue; }
  code=$(curl -s -o "$OUT/report-$k.html" -w '%{http_code}' "$BASE$href")
  [ "$code" = 200 ] && grep -q '<article>' "$OUT/report-$k.html" || fail "$href -> $code"
  ok "$href"
done

# 5. bad input is refused, never served
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/report?job=crm&f=../../departments.json")" = 400 ] || fail "path traversal not refused"
[ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE/report?job=nope&f=x.md")" = 400 ] || fail "unknown job not refused"
ok "bad requests -> 400"

# 6. screenshot of the home page (Chrome headless; look at it)
"$CHROME" --headless=new --disable-gpu --no-first-run --hide-scrollbars --window-size=1200,900 \
  --screenshot="$OUT/home.png" "$BASE/" >/dev/null 2>&1
[ -s "$OUT/home.png" ] && ok "screenshot $OUT/home.png" || fail "no screenshot"

# 7. optional: PDF of the sales pulse
if [ "${1:-}" = "--pdf" ]; then
  ct=$(curl -s -o "$OUT/sales-pulse.pdf" -w '%{content_type}' "$BASE/pdf?job=sales&f=pulse.md")
  [ "$ct" = application/pdf ] && ok "pdf $OUT/sales-pulse.pdf ($(wc -c <"$OUT/sales-pulse.pdf") bytes)" || fail "/pdf returned $ct"
fi
echo "all good; outputs in $OUT"
