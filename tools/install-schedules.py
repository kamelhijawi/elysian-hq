#!/usr/bin/env python3
"""Generate and load one launchd job per schedule entry in departments.json. --check only reports."""
import json, pathlib, subprocess, sys
HOME=pathlib.Path.home(); LA=HOME/"Library/LaunchAgents"; HQ=HOME/"elysian/hq"
m=json.load(open(HQ/"departments.json")); check="--check" in sys.argv
want={}
for d in m["departments"]+([m["centre"]] if isinstance(m.get("centre"),dict) else []):
    for i,s in enumerate(d.get("schedule",[])):
        label=f"com.elysian.{d['id']}.{i}"
        cal="".join(f"<dict><key>Weekday</key><integer>{wd}</integer><key>Hour</key><integer>{s['hour']}</integer><key>Minute</key><integer>{s['minute']}</integer></dict>" for wd in s["days"])
        want[label]=f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{label}</string>
<key>ProgramArguments</key><array><string>/bin/zsh</string><string>{HQ}/tools/run-dept.sh</string><string>{d['id']}</string><string>{s['recipe']}</string></array>
<key>StartCalendarInterval</key><array>{cal}</array>
<key>StandardOutPath</key><string>{HOME}/Library/Logs/elysian-{d['id']}.log</string>
<key>StandardErrorPath</key><string>{HOME}/Library/Logs/elysian-{d['id']}.log</string>
<key>RunAtLoad</key><false/>
</dict></plist>
"""
# services: always-on local processes (the reports page). Started at login, restarted only if they exit with an error.
for s in m.get("services",[]):
    label=f"com.elysian.svc.{s['id']}"
    args="".join(f"<string>{a}</string>" for a in s["command"])
    want[label]=f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{label}</string>
<key>ProgramArguments</key><array>{args}</array>
<key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:{HOME}/.local/bin</string></dict>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
<key>StandardOutPath</key><string>{HOME}/Library/Logs/elysian-svc-{s['id']}.log</string>
<key>StandardErrorPath</key><string>{HOME}/Library/Logs/elysian-svc-{s['id']}.log</string>
</dict></plist>
"""
have={p.stem:p for p in LA.glob("com.elysian.*.plist")}
for label,p in have.items():
    if label not in want:
        print("remove",label)
        if not check: subprocess.call(["launchctl","unload",str(p)],stderr=subprocess.DEVNULL); p.unlink()
for label,xml in want.items():
    p=LA/f"{label}.plist"; same=p.exists() and p.read_text()==xml
    print(("ok    " if same else "install"),label)
    if not check and not same:
        if p.exists(): subprocess.call(["launchctl","unload",str(p)],stderr=subprocess.DEVNULL)
        p.write_text(xml); subprocess.call(["launchctl","load",str(p)])
