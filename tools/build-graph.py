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

data={"now":now,"engine":engine,"xai":xai,"xai_credits":xai_credits,
 "sales":{"commits":S["commits"],"last":S["last"],"agents":agents,"devs":devs,"recipes":len(S["recipes"]),"open":S["open"],"closed":S["closed"],"briefs":len(briefs),"blanks":S["blanks"],"monday_last":monday_last},
 "marketing":{"commits":M["commits"],"last":M["last"],"roles":len(M["recipes"]),"role_names":sorted(M["recipes"]),"ideas":ideas_n,"unused":ideas_unused,"plans":len(plans),"open":M["open"],"closed":M["closed"],"blanks":M["blanks"]},
 "edges":[{"file":r,"roles":sorted(v)} for r,v in edge_rows]}
mk_log=pathlib.Path.home()/"Library/Logs/elysian-marketing-bot.log"
data["marketing"]["bot_last"]=datetime.datetime.fromtimestamp(mk_log.stat().st_mtime).strftime("%Y-%m-%d %H:%M") if mk_log.exists() else "scheduled, not yet run"
# last grok run from marketing week.md stamps
wk=(DEPTS["marketing"]/"live/week.md").read_text(errors="ignore") if (DEPTS["marketing"]/"live/week.md").exists() else ""
gr=re.findall(r"<!-- grokbot (\S+) (\S+ \S+) tokens=(\d+) -->",wk)
data["marketing"]["grok_last"]={"model":gr[-1][0],"when":gr[-1][1],"tokens":int(gr[-1][2])} if gr else None
J=json.dumps(data)
page="""<title>Elysian Orbit</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#04080C;--ink:#EAF2F3;--ink2:#8FA6AC;--dim:#4F636B;--line:#1B2F38;--teal:#39C9B6;--gold:#E0B45C;--green:#7BD3A0;--red:#F08C84}
*{box-sizing:border-box} html{color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "IBM Plex Sans",system-ui,sans-serif;min-height:100vh;overflow-x:hidden}
.sky{position:fixed;inset:0;z-index:0;background:radial-gradient(1200px 800px at 50% 45%,#0B1B24 0%,#04080C 65%)}
.sky canvas{position:absolute;inset:0;width:100%;height:100%}
.wrap{position:relative;z-index:1;max-width:1500px;margin:0 auto;padding:30px 36px 50px}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;flex-wrap:wrap}
.brand{font:500 12px "IBM Plex Mono",monospace;letter-spacing:.22em;text-transform:uppercase;color:var(--teal)}
h1{font:400 clamp(34px,4.4vw,56px)/1 "DM Serif Display",Georgia,serif;margin:6px 0 0;letter-spacing:-.015em}
h1 i{font-style:italic;color:var(--gold)}
.sub{color:var(--ink2);font-size:14px;margin-top:8px;max-width:62ch}
.live{display:flex;align-items:center;gap:10px;font:500 12px "IBM Plex Mono",monospace;color:var(--ink2);letter-spacing:.08em;text-transform:uppercase}
.dot{width:10px;height:10px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(123,211,160,.6)}70%{box-shadow:0 0 0 12px rgba(123,211,160,0)}100%{box-shadow:0 0 0 0 rgba(123,211,160,0)}}
figure{margin:10px auto 0;max-width:1100px}
svg.orbit{width:100%;height:auto;display:block;overflow:visible}
.orbit text{font-family:"IBM Plex Sans",system-ui,sans-serif}
.mono{font-family:"IBM Plex Mono",monospace}
@keyframes spin{to{transform:rotate(360deg)}} @keyframes unspin{to{transform:rotate(-360deg)}}
.o1{animation:spin 90s linear infinite;transform-origin:0 0}
.o1b{animation:spin 90s linear infinite;transform-origin:0 0;animation-delay:-45s}
.u1{animation:unspin 90s linear infinite;transform-origin:0 0}
.u1b{animation:unspin 90s linear infinite;transform-origin:0 0;animation-delay:-45s}
.moon{animation:spin 14s linear infinite;transform-origin:0 0}
.umoon{animation:unspin 14s linear infinite;transform-origin:0 0}
.sat{animation:spin 22s linear infinite;transform-origin:0 0}
.usat{animation:unspin 22s linear infinite;transform-origin:0 0}
@media(prefers-reduced-motion:reduce){.o1,.o1b,.u1,.u1b,.moon,.umoon,.sat,.usat{animation:none}}
.panel{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1100px;margin:6px auto 0}
.card{border:1px solid var(--line);border-radius:16px;padding:18px 20px;background:rgba(9,20,26,.72);backdrop-filter:blur(6px)}
.card h2{font:400 22px "DM Serif Display",Georgia,serif;margin:0 0 2px}
.card .meta{font:400 12px "IBM Plex Mono",monospace;color:var(--ink2)}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
.tile{background:rgba(4,8,12,.6);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.tile .v{font:500 26px/1 "IBM Plex Sans",sans-serif;font-variant-numeric:tabular-nums}
.tile .k{font-size:11px;color:var(--ink2);margin-top:5px}
.card.s .tile .v{color:#CFF5EE}.card.m .tile .v{color:#F5E6C2}.tile.warn .v{color:var(--gold)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{font:400 11.5px "IBM Plex Mono",monospace;border:1px solid var(--line);border-radius:999px;padding:3px 9px;color:var(--ink)}
.chip b{color:var(--ink2);font-weight:400}
.foot{max-width:1100px;margin:18px auto 0;color:var(--dim);font-size:12px;display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
.foot a{color:var(--teal);text-decoration:none}
@media(max-width:820px){.panel{grid-template-columns:1fr}}
</style>
<div class="sky"><canvas id="stars"></canvas></div>
<div class="wrap">
<header>
  <div><div class="brand">Elysian · HQ</div><h1>Two departments in <i>orbit.</i></h1><div class="sub">Orbit at the centre. Sales and marketing circle it; each department's bot circles its department. Numbers are read from the files at build time.</div></div>
  <div class="live"><span class="dot"></span><span id="stamp"></span></div>
</header>
<figure>
<svg class="orbit" viewBox="-560 -420 1120 840" role="img" aria-label="Orbit diagram: Orbit, the HQ, at the centre; the sales and marketing departments orbit him on one ring; each department has a bot moon; marketing has five role satellites.">
 <defs>
  <radialGradient id="sun" cx="40%" cy="35%" r="70%"><stop offset="0" stop-color="#FFF7E0"/><stop offset=".45" stop-color="#E0B45C"/><stop offset="1" stop-color="#6E5220"/></radialGradient>
  <radialGradient id="ps" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#BFF3EB"/><stop offset=".5" stop-color="#39C9B6"/><stop offset="1" stop-color="#0E4B45"/></radialGradient>
  <radialGradient id="pm" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#FFEBC2"/><stop offset=".5" stop-color="#E0B45C"/><stop offset="1" stop-color="#5A4419"/></radialGradient>
  <radialGradient id="moon" cx="35%" cy="30%" r="75%"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".6" stop-color="#B9C7CC"/><stop offset="1" stop-color="#4E5E64"/></radialGradient>
  <filter id="glow"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <filter id="glow2"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
 </defs>
 <!-- orbit ring -->
 <circle r="330" fill="none" stroke="#1B2F38" stroke-width="1.2" stroke-dasharray="2 7"/>
 <circle r="330" fill="none" stroke="#39C9B6" stroke-opacity=".08" stroke-width="26"/>
 <!-- sun: Kamel -->
 <g filter="url(#glow)"><circle r="62" fill="url(#sun)"/></g>
 <circle r="80" fill="none" stroke="#E0B45C" stroke-opacity=".25" stroke-width="1"/>
 <text y="-4" text-anchor="middle" font-family="DM Serif Display, Georgia, serif" font-size="24" fill="#1A1206">Orbit</text>
 <text y="16" text-anchor="middle" font-size="10.5" fill="#3A2A0A">Elysian HQ</text>
 <!-- SALES planet on ring -->
 <g class="o1"><g transform="translate(330,0)">
   <g class="u1">
     <g filter="url(#glow2)"><circle r="46" fill="url(#ps)"/></g>
     <text y="-56" text-anchor="middle" font-family="DM Serif Display, Georgia, serif" font-size="20" fill="#EAF2F3">Sales</text>
     <text y="5" text-anchor="middle" font-size="22" font-weight="600" fill="#05201C" id="p-s-1"></text>
     <text y="21" text-anchor="middle" font-size="9.5" fill="#05201C">agents</text>
     <text y="70" text-anchor="middle" class="mono" font-size="10.5" fill="#8FA6AC" id="p-s-2"></text>
     <text y="84" text-anchor="middle" class="mono" font-size="10.5" fill="#8FA6AC" id="p-s-3"></text>
     <!-- moon: sales bot -->
     <circle r="88" fill="none" stroke="#39C9B6" stroke-opacity=".25" stroke-dasharray="1 5"/>
     <g class="moon"><g transform="translate(88,0)"><g class="umoon">
       <circle r="11" fill="url(#moon)"/><text y="-16" text-anchor="middle" font-size="9.5" fill="#CFF5EE">Monday bot</text>
       <text y="26" text-anchor="middle" class="mono" font-size="8.5" fill="#8FA6AC" id="p-s-bot"></text>
     </g></g></g>
   </g>
 </g></g>
 <!-- MARKETING planet opposite -->
 <g class="o1b"><g transform="translate(330,0)">
   <g class="u1b">
     <g filter="url(#glow2)"><circle r="46" fill="url(#pm)"/></g>
     <text y="-56" text-anchor="middle" font-family="DM Serif Display, Georgia, serif" font-size="20" fill="#EAF2F3">Marketing</text>
     <text y="5" text-anchor="middle" font-size="22" font-weight="600" fill="#2A1E06" id="p-m-1"></text>
     <text y="21" text-anchor="middle" font-size="9.5" fill="#2A1E06">ideas</text>
     <text y="70" text-anchor="middle" class="mono" font-size="10.5" fill="#8FA6AC" id="p-m-2"></text>
     <text y="84" text-anchor="middle" class="mono" font-size="10.5" fill="#8FA6AC" id="p-m-3"></text>
     <circle r="88" fill="none" stroke="#E0B45C" stroke-opacity=".25" stroke-dasharray="1 5"/>
     <g class="moon"><g transform="translate(88,0)"><g class="umoon">
       <circle r="11" fill="url(#moon)"/><text y="-16" text-anchor="middle" font-size="9.5" fill="#F5E6C2">Grok bot</text>
       <text y="26" text-anchor="middle" class="mono" font-size="8.5" fill="#8FA6AC" id="p-m-bot"></text>
     </g></g></g>
     <!-- role satellites -->
     <circle r="122" fill="none" stroke="#E0B45C" stroke-opacity=".14" stroke-dasharray="1 6"/>
     <g id="sats"></g>
   </g>
 </g></g>
 <!-- flow arcs between planets (along the ring) -->
 <text x="0" y="-352" text-anchor="middle" class="mono" font-size="10.5" fill="#39C9B6">marketing reads sales facts · plans come back · marketing never writes to sales</text>
</svg>
</figure>
<div class="panel">
 <div class="card s"><h2>Sales · brain/</h2><div class="meta" id="s-meta"></div><div class="tiles" id="s-tiles"></div></div>
 <div class="card m"><h2>Marketing · marketing-brain/</h2><div class="meta" id="m-meta"></div><div class="tiles" id="m-tiles"></div><div class="chips" id="edges"></div></div>
</div>
<div class="foot"><span>Rebuilt on every commit in either brain · <a href="https://github.com/kamelhijawi/elysian-hq">kamelhijawi/elysian-hq</a></span><span id="engine"></span></div>
</div>
<script>
const D=__DATA__;const $=s=>document.querySelector(s);
$('#stamp').textContent='live · built '+D.now;$('#engine').textContent='engine: '+D.engine;
const s=D.sales,m=D.marketing;
$('#p-s-1').textContent=s.agents;$('#p-s-2').textContent=`${s.devs} developers · ${s.open} open actions`;$('#p-s-3').textContent=`${s.briefs} brief · ${s.blanks} blanks`;
$('#p-s-bot').textContent='last '+(s.monday_last||'never');
$('#p-m-1').textContent=m.ideas;$('#p-m-2').textContent=`${m.roles} roles · ${m.plans} plan · ${m.open} open actions`;$('#p-m-3').textContent=`${m.unused} ideas unused · ${m.blanks} blanks`;
$('#p-m-bot').textContent=m.grok_last?`${m.grok_last.model} · ${(m.grok_last.tokens/1000).toFixed(0)}k tok`:'not yet run';
const names=m.role_names;const g=$('#sats');
g.innerHTML=names.map((n,i)=>{const a=(i/names.length)*360;return `<g class="sat" style="animation-delay:${-i*22/names.length}s"><g transform="rotate(${a}) translate(122,0) rotate(${-a})"><g class="usat" style="animation-delay:${-i*22/names.length}s"><circle r="4.5" fill="#E0B45C"/><text y="-9" text-anchor="middle" font-size="8.5" fill="#F5E6C2">${n}</text></g></g></g>`}).join('');
const tile=(v,k,c='')=>`<div class="tile ${c}"><div class="v">${v}</div><div class="k">${k}</div></div>`;
$('#s-meta').textContent=`${s.commits} commits · last ${s.last} · Monday bot last run ${s.monday_last}`;
$('#s-tiles').innerHTML=tile(s.agents,'agents')+tile(s.devs,'active developers')+tile(s.recipes,'recipes')+tile(s.open,'open actions',s.open>5?'warn':'')+tile(s.briefs,'Monday briefs')+tile(s.blanks,'blanks to fill','warn');
$('#m-meta').textContent=`${m.commits} commits · last ${m.last} · Grok bot ${m.grok_last?('last run '+m.grok_last.when):'scheduled Sunday 08:00'}`;
$('#m-tiles').innerHTML=tile(m.roles,'roles')+tile(m.ideas,'ideas in the bank')+tile(m.unused,'ideas unused','warn')+tile(m.plans,'plans issued')+tile(m.open,'open actions',m.open>5?'warn':'')+tile(m.blanks,'blanks to fill','warn');
$('#edges').innerHTML=D.edges.map(e=>`<span class="chip">${e.file.replace(/^(ref|do|live)\\//,'')} <b>← ${e.roles.join(', ')}</b></span>`).join('');
// starfield
const c=$('#stars'),x=c.getContext('2d');function stars(){c.width=innerWidth;c.height=innerHeight;x.clearRect(0,0,c.width,c.height);for(let i=0;i<Math.floor(c.width*c.height/6000);i++){const r=Math.random();x.fillStyle=`rgba(${r>.9?'224,180,92':'190,220,230'},${(.15+Math.random()*.6).toFixed(2)})`;x.beginPath();x.arc(Math.random()*c.width,Math.random()*c.height,Math.random()*1.4+.2,0,7);x.fill();}}
stars();addEventListener('resize',stars);
</script>
"""
page=page.replace("__DATA__",J)
(HQ/"index.html").write_text(page,encoding="utf-8")
print(json.dumps({"engine":engine,"agents":agents,"edges":len(edge_rows),"grok_last":data["marketing"]["grok_last"]}))
