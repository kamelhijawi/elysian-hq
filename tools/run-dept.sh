#!/bin/zsh
# run-dept.sh <dept-id> <recipe>  — runs one department recipe on Claude headless, with heartbeat.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
HQ="/Users/kamel/elysian/hq"; DEPT="$1"; RECIPE="$2"; TODAY=$(date +%Y-%m-%d)
read -r FOLDER TOOLS <<< "$(python3 - "$DEPT" <<'PY'
import json,sys
m=json.load(open('/Users/kamel/elysian/hq/departments.json'))
c=m.get('centre',{})
d=([x for x in m['departments'] if x['id']==sys.argv[1]] or [c])[0]
print(d['folder'], ",".join(d['tools']))
PY
)"
cd "/Users/kamel/elysian/$FOLDER" || { python3 $HQ/tools/heartbeat.py "$DEPT" failed "folder missing"; exit 1; }
# Monday brief guard: don't duplicate a brief that already exists
if [ "$RECIPE" = "do/weekly-meeting.md" ] && [ -f "live/briefs/$TODAY.md" ]; then python3 $HQ/tools/heartbeat.py "$DEPT" ok "brief $TODAY already exists"; exit 0; fi
python3 $HQ/tools/heartbeat.py "$DEPT" running "$RECIPE"
PROMPT="You are the $DEPT department bot for Elysian. Moon Shelter is Kamel; you report to him. Today is $TODAY. Read CLAUDE.md in this folder, then run the recipe $RECIPE exactly: load the files it names, follow its sequence, write the outputs it names, then run: git add -A && git commit -m \"$DEPT: $(basename $RECIPE .md) $TODAY\". Read-only toward Salesforce and Gmail. Never send anything. Never write outside this folder. Follow the "Working with the other departments and Moon Shelter" protocol in CLAUDE.md if present: read decisions and incoming handoffs first, write your handoffs and live/report.md last. If a data source is unreachable, write what you could not get into the output and still commit. Finish with one line: DONE <files written>."
claude -p "$PROMPT" --output-format text --allowedTools "$TOOLS" < /dev/null
RC=$?
python3 $HQ/tools/collect-report.py "$DEPT"
if [ $RC -eq 0 ]; then python3 $HQ/tools/heartbeat.py "$DEPT" ok "$(basename $RECIPE .md) $TODAY"; else python3 $HQ/tools/heartbeat.py "$DEPT" failed "exit $RC on $RECIPE"; fi
