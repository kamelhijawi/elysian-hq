#!/bin/zsh
# run-ondemand.sh <dept-id> <recipe> [bot-name] — runs one recipe on Claude headless without the scheduled-run side effects
# (no Moon Shelter inbox copy, no Monday guard). Used by report-server.py for the "Generate report" buttons.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin:$PATH"
HQ="/Users/kamel/elysian/hq"; DEPT="$1"; RECIPE="$2"; BOT="${3:-$DEPT-ondemand}"; TODAY=$(date +%Y-%m-%d); NOW=$(date +%H:%M)
read -r FOLDER TOOLS <<< "$(python3 - "$DEPT" <<'PY'
import json,sys
m=json.load(open('/Users/kamel/elysian/hq/departments.json'))
c=m.get('centre',{})
d=([x for x in m['departments'] if x['id']==sys.argv[1]] or [c])[0]
print(d['folder'], ",".join(d['tools']))
PY
)"
cd "/Users/kamel/elysian/$FOLDER" || { python3 $HQ/tools/heartbeat.py "$BOT" failed "folder missing"; exit 1; }
python3 $HQ/tools/heartbeat.py "$BOT" running "$RECIPE"
PROMPT="You are the $DEPT department bot for Elysian. Moon Shelter is Kamel; you report to him. Today is $TODAY, the time is $NOW Dubai. This is an ON-DEMAND run started by Kamel from the reports page. Read CLAUDE.md in this folder, then run the recipe $RECIPE exactly: load the files it names, follow its sequence, write the outputs it names, then commit as the recipe says. Read-only toward Salesforce and Gmail. Never send anything. Never write outside this folder. Do not overwrite live/report.md or live/handoffs/ unless the recipe says so. If a data source is unreachable, write what you could not get into the output and still commit. Finish with one line: DONE <files written>."
claude -p "$PROMPT" --output-format text --allowedTools "$TOOLS" < /dev/null
RC=$?
if [ $RC -eq 0 ]; then python3 $HQ/tools/heartbeat.py "$BOT" ok "$(basename $RECIPE .md) $TODAY $NOW"; else python3 $HQ/tools/heartbeat.py "$BOT" failed "exit $RC on $RECIPE"; fi
exit $RC
