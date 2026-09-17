#!/usr/bin/env python3
"""collect-report.py <dept> — copy the department's live/report.md into Moon Shelter's inbox (deterministic, no AI)."""
import sys, json, pathlib, datetime, subprocess
E=pathlib.Path.home()/"elysian"; m=json.load(open(E/"hq/departments.json"))
dept=sys.argv[1]; d=[x for x in m["departments"] if x["id"]==dept]
if not d: sys.exit(0)
src=E/d[0]["folder"]/"live/report.md"
if not src.exists(): print("no report from",dept); sys.exit(0)
inbox=E/"moonshelter/live/inbox"; inbox.mkdir(parents=True,exist_ok=True)
dst=inbox/f"{datetime.date.today().isoformat()}-{dept}.md"; dst.write_text(src.read_text())
subprocess.call("git add -A && git commit -q -m 'inbox: %s report %s'"%(dept,datetime.date.today().isoformat()),cwd=E/"moonshelter",shell=True)
print("collected",dst.name)
