#!/usr/bin/env python3
"""Live department graph. Reads ../brain and ../marketing-brain, writes index.html. Run from hq/."""
import re, subprocess, datetime, pathlib, html, json, os
HQ=pathlib.Path(__file__).resolve().parent.parent
DEPTS={"sales":HQ.parent/"brain","marketing":HQ.parent/"marketing-brain"}
# allow CI checkout layout: hq/deps/brain, hq/deps/marketing-brain
for k,p in list(DEPTS.items()):
    alt=HQ/"deps"/("brain" if k=="sales" else "marketing-brain")
    if not p.exists() and alt.exists(): DEPTS[k]=alt
def sh(cmd,cwd):
    try: return subprocess.check_output(cmd,cwd=cwd,shell=True,text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return ""
def esc(s): return html.escape(str(s))
def stats(root):
    md=list(root.rglob("*.md")); md=[m for m in md if ".git" not in m.parts]
    blanks=sum(len(re.findall(r"<< ?fill",m.read_text(errors="ignore"))) for m in md)
    recipes=[p.stem for p in (root/"do").glob("*.md")] if (root/"do").exists() else []
    acts=(root/"live/actions.md"); open_n=closed_n=0
    if acts.exists():
        for l in acts.read_text().splitlines():
            if "| OPEN |" in l: open_n+=1
            elif "| CLOSED |" in l or "| DROPPED |" in l: closed_n+=1
    last=sh("git log -1 --format=%cd --date=format:'%Y-%m-%d %H:%M'",root)
    commits=sh("git rev-list --count HEAD",root)
    return dict(files=len(md),blanks=blanks,recipes=recipes,open=open_n,closed=closed_n,last=last,commits=commits)
S=stats(DEPTS["sales"]); M=stats(DEPTS["marketing"])
# sales extras
team=(DEPTS["sales"]/"ref/team.md").read_text(errors="ignore")
agents=sum(1 for l in team.splitlines() if l.startswith("| ") and ("005Vn" in l or "not in Salesforce" in l) and "Team 2 agents" not in l)
devs=sum(1 for l in (DEPTS["sales"]/"ref/developers.md").read_text(errors="ignore").splitlines() if l.startswith("| ") and "| Active |" in l)
briefs=sorted((DEPTS["sales"]/"live/briefs").glob("2026-*.md")) if (DEPTS["sales"]/"live/briefs").exists() else []
# marketing extras
ideas=(DEPTS["marketing"]/"live/ideas.md").read_text(errors="ignore") if (DEPTS["marketing"]/"live/ideas.md").exists() else ""
ideas_n=sum(1 for l in ideas.splitlines() if l.startswith("2026-"))
ideas_unused=sum(1 for l in ideas.splitlines() if l.startswith("2026-") and "| UNUSED |" in l)
plans=[p.stem for p in (DEPTS["marketing"]/"live/plans").glob("*.md")] if (DEPTS["marketing"]/"live/plans").exists() else []
# cross links: marketing recipes that LOAD ../brain files
edges={}
for rp in (DEPTS["marketing"]/"do").glob("*.md"):
    t=rp.read_text(errors="ignore")
    for ref in re.findall(r"\.\./brain/([\w/.-]+)",t):
        edges.setdefault(ref,set()).add(rp.stem)
edge_rows=sorted(edges.items())
# bots
monday_log=pathlib.Path.home()/"Library/Logs/elysian-brain-monday.log"
monday_last=datetime.datetime.fromtimestamp(monday_log.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if monday_log.exists() else "never"
xai=subprocess.call("security find-generic-password -s xai-api-key >/dev/null 2>&1",shell=True)==0
xai_credits=(pathlib.Path.home()/".config/xai/credits-ok").exists()
engine=("Grok (xAI)" if xai_credits else "Grok key stored, no credits yet; running on Claude") if xai else "Claude headless (Grok key not set)"
now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
def edge_svg():
    out=[]; y=300
    for ref,srcs in edge_rows:
        out.append(f'<text x="700" y="{y}" text-anchor="middle" fill="#8FA6AC" font-size="11">{esc(ref)} ← {esc(", ".join(sorted(srcs)))}</text>'); y+=16
    return "\n".join(out), y
edge_text,_=edge_svg()
page=f"""<title>Elysian Departments</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono&display=swap">
<style>
:root{{--bg:#0B1418;--bg2:#10202A;--panel:#13242D;--ink:#E7F0F1;--ink2:#8FA6AC;--line:#26404A;--accent:#39C9B6;--gold:#E0B45C;--bad:#F08C84}}
*{{box-sizing:border-box}} html{{color-scheme:dark}}
body{{background:radial-gradient(1200px 700px at 50% 30%,var(--bg2),var(--bg) 70%);color:var(--ink);font:15px/1.5 "IBM Plex Sans",system-ui,sans-serif;margin:0;padding:28px 32px 40px;min-height:100vh}}
header{{max-width:1400px;margin:0 auto 14px;display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap}}
h1{{font:400 40px/1.05 "DM Serif Display",Georgia,serif;margin:0}}
.sub{{color:var(--ink2);font-size:14px;margin-top:6px}} .stamp{{font-size:12px;color:var(--ink2);text-align:right;font-family:"IBM Plex Mono",monospace}}
figure{{margin:0 auto;max-width:1400px}} svg{{max-width:100%;height:auto;display:block}}
figcaption{{color:var(--ink2);font-size:13px;margin-top:10px;max-width:80ch}}
.tbl{{max-width:1400px;margin:18px auto 0;overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13.5px}}
th{{text-align:left;color:var(--ink2);font-size:12px;text-transform:uppercase;letter-spacing:.06em;padding:6px 10px;border-bottom:1px solid var(--line)}} td{{padding:7px 10px;border-bottom:1px solid var(--line)}} .mono{{font-family:"IBM Plex Mono",monospace}}
</style>
<header><div><h1>Elysian departments, live</h1><div class="sub">Two AI departments reporting to Kamel, and what flows between them. Rebuilt from the files on every change.</div></div><div class="stamp">built {now}<br>engine: {esc(engine)}</div></header>
<figure>
<svg viewBox="0 0 1400 640" role="img" aria-label="Kamel at top; the sales department and the marketing department below, each with live counts; arrows show that marketing reads sales facts and hands plans back; each department has a bot that runs its recipes." xmlns="http://www.w3.org/2000/svg" font-family="IBM Plex Sans, system-ui, sans-serif" font-size="13">
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#39C9B6"/></marker>
<marker id="g" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0 0L10 5L0 10z" fill="#E0B45C"/></marker>
<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="5" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
<rect x="560" y="24" width="280" height="70" rx="12" fill="#13242D" stroke="#E7F0F1" stroke-width="1.5"/>
<text x="700" y="54" text-anchor="middle" font-family="DM Serif Display, Georgia, serif" font-size="22" fill="#E7F0F1">Kamel</text>
<text x="700" y="76" text-anchor="middle" fill="#8FA6AC" font-size="12">Head of Sales · owns both departments · approves every plan, send and spend</text>
<line x1="700" y1="94" x2="700" y2="130" stroke="#8FA6AC" stroke-width="1.5"/><line x1="330" y1="130" x2="1070" y2="130" stroke="#8FA6AC" stroke-width="1.5"/>
<line x1="330" y1="130" x2="330" y2="160" stroke="#8FA6AC" stroke-width="1.5"/><line x1="1070" y1="130" x2="1070" y2="160" stroke="#8FA6AC" stroke-width="1.5"/>

<rect x="80" y="160" width="500" height="330" rx="14" fill="#13242D" stroke="#39C9B6" filter="url(#glow)"/>
<text x="100" y="190" font-family="DM Serif Display, Georgia, serif" font-size="22" fill="#E7F0F1">Sales department</text>
<text x="100" y="210" fill="#8FA6AC" font-size="12" font-family="IBM Plex Mono, monospace">brain/ · {S['commits']} commits · last {esc(S['last'])}</text>
<g font-size="13" fill="#E7F0F1">
<text x="100" y="242">Agents on the floor</text><text x="560" y="242" text-anchor="end" font-family="IBM Plex Mono, monospace">{agents}</text>
<text x="100" y="264">Active developers</text><text x="560" y="264" text-anchor="end" font-family="IBM Plex Mono, monospace">{devs}</text>
<text x="100" y="286">Recipes</text><text x="560" y="286" text-anchor="end" font-family="IBM Plex Mono, monospace">{len(S['recipes'])}</text>
<text x="100" y="308">Open actions / closed</text><text x="560" y="308" text-anchor="end" font-family="IBM Plex Mono, monospace">{S['open']} / {S['closed']}</text>
<text x="100" y="330">Monday briefs written</text><text x="560" y="330" text-anchor="end" font-family="IBM Plex Mono, monospace">{len(briefs)}</text>
<text x="100" y="352">Blanks still to fill</text><text x="560" y="352" text-anchor="end" font-family="IBM Plex Mono, monospace">{S['blanks']}</text>
</g>
<rect x="100" y="380" width="460" height="90" rx="8" fill="#0F1C22" stroke="#26404A"/>
<text x="116" y="404" font-size="14" font-weight="600" fill="#E7F0F1">Sales bot</text><text x="544" y="404" text-anchor="end" fill="#39C9B6" font-size="12">Monday 07:00</text>
<text x="116" y="424" fill="#8FA6AC" font-size="12">Runs do/weekly-meeting.md: Salesforce + DLD digest → brief, week log, actions</text>
<text x="116" y="444" fill="#8FA6AC" font-size="12">Engine: {esc(engine)}</text>
<text x="116" y="462" fill="#8FA6AC" font-size="12" font-family="IBM Plex Mono, monospace">last run log: {esc(monday_last)}</text>

<rect x="820" y="160" width="500" height="330" rx="14" fill="#13242D" stroke="#E0B45C" filter="url(#glow)"/>
<text x="840" y="190" font-family="DM Serif Display, Georgia, serif" font-size="22" fill="#E7F0F1">Marketing department</text>
<text x="840" y="210" fill="#8FA6AC" font-size="12" font-family="IBM Plex Mono, monospace">marketing-brain/ · {M['commits']} commits · last {esc(M['last'])}</text>
<g font-size="13" fill="#E7F0F1">
<text x="840" y="242">Roles (strategy and creative)</text><text x="1300" y="242" text-anchor="end" font-family="IBM Plex Mono, monospace">{len(M['recipes'])}</text>
<text x="840" y="264">Ideas in the bank / unused</text><text x="1300" y="264" text-anchor="end" font-family="IBM Plex Mono, monospace">{ideas_n} / {ideas_unused}</text>
<text x="840" y="286">Plans issued</text><text x="1300" y="286" text-anchor="end" font-family="IBM Plex Mono, monospace">{len(plans)}</text>
<text x="840" y="308">Open actions / closed</text><text x="1300" y="308" text-anchor="end" font-family="IBM Plex Mono, monospace">{M['open']} / {M['closed']}</text>
<text x="840" y="330">Budget</text><text x="1300" y="330" text-anchor="end" font-family="IBM Plex Mono, monospace">TBA (AED 0)</text>
<text x="840" y="352">Blanks still to fill</text><text x="1300" y="352" text-anchor="end" font-family="IBM Plex Mono, monospace">{M['blanks']}</text>
</g>
<rect x="840" y="380" width="460" height="90" rx="8" fill="#0F1C22" stroke="#26404A"/>
<text x="856" y="404" font-size="14" font-weight="600" fill="#E7F0F1">Marketing bot</text><text x="1284" y="404" text-anchor="end" fill="#E0B45C" font-size="12">Sun analyst+ideas · Mon 06:30 report</text>
<text x="856" y="424" fill="#8FA6AC" font-size="12">Runs {esc(", ".join(sorted(M['recipes'])))}</text>
<text x="856" y="444" fill="#8FA6AC" font-size="12">Engine: {esc(engine)}</text>
<text x="856" y="462" fill="#8FA6AC" font-size="12" font-family="IBM Plex Mono, monospace">plans, ideas, media plans → Kamel → named executor</text>

<path d="M580 260 C 640 260, 760 260, 820 260" fill="none" stroke="#39C9B6" stroke-width="2.5" marker-end="url(#a)"/>
<text x="700" y="250" text-anchor="middle" fill="#39C9B6" font-size="11">marketing reads: developers, launches, voice, numbers, team</text>
<path d="M820 400 C 760 400, 640 400, 580 400" fill="none" stroke="#E0B45C" stroke-width="2.5" stroke-dasharray="7 6" marker-end="url(#g)"/>
<text x="700" y="392" text-anchor="middle" fill="#E0B45C" font-size="11">marketing hands back: launch plans, media plans, the marketing line in the Monday brief</text>
{edge_text}
<text x="700" y="620" text-anchor="middle" fill="#8FA6AC" font-size="12">Marketing may read the sales brain and never writes to it. Both departments commit to git; this page is rebuilt from those commits.</text>
</svg>
<figcaption>Live counts from both folders. Blanks are fields still waiting for a fact. The cross-links listed in the middle are parsed from the marketing recipes: every sales file a marketing role loads.</figcaption>
</figure>
<div class="tbl"><table><thead><tr><th>Sales file read by marketing</th><th>Marketing roles that load it</th></tr></thead><tbody>
{"".join(f"<tr><td class=mono>{esc(r)}</td><td>{esc(', '.join(sorted(s)))}</td></tr>" for r,s in edge_rows)}
</tbody></table></div>
"""
(HQ/"index.html").write_text(page,encoding="utf-8")
print(json.dumps({"sales":{k:v for k,v in S.items() if k!='recipes'},"marketing":{k:v for k,v in M.items() if k!='recipes'},"agents":agents,"devs":devs,"ideas":ideas_n,"plans":len(plans),"edges":len(edge_rows),"engine":engine}))
