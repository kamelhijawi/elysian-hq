#!/usr/bin/env python3
"""heartbeat.py <bot> <running|ok|failed> [note] — records bot state in hq/status.json, rebuilds the graph, pushes."""
import sys, json, pathlib, datetime, subprocess, time, os
HQ=pathlib.Path(__file__).resolve().parent.parent; f=HQ/"status.json"
LOCK=HQ/".git/hq.lock"
for _ in range(60):
    try: os.mkdir(LOCK); break
    except FileExistsError: time.sleep(1)
st=json.loads(f.read_text()) if f.exists() else {}
bot,state=sys.argv[1],sys.argv[2]; note=" ".join(sys.argv[3:])
now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
b=st.get(bot,{}); b["state"]=state; b["note"]=note
if state=="running": b["started"]=now
else: b["finished"]=now; b["last_ok"]=now if state=="ok" else b.get("last_ok")
st[bot]=b; f.write_text(json.dumps(st,indent=1))
subprocess.call(["python3",str(HQ/"tools/build-graph.py")],stdout=subprocess.DEVNULL)
subprocess.call("git add -A && git commit -q -m 'heartbeat: %s %s' && git push -q origin main"%(bot,state),cwd=HQ,shell=True)
try: os.rmdir(LOCK)
except OSError: pass
