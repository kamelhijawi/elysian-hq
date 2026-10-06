#!/usr/bin/env python3
"""Moon Shelter reports page. Local only (127.0.0.1:8770). Press a button, a department bot runs its on-demand recipe
on Claude headless, and the report renders here as a web page. Nothing here is public; reports contain names."""
import http.server, json, pathlib, subprocess, threading, datetime, html, re, urllib.parse, sys, time
from marketing_workspace import snapshot as marketing_snapshot
E=pathlib.Path.home()/"elysian"; HQ=E/"hq"; PORT=8770
# button id -> (dept, recipe, bot name, where the output files land, label)
JOBS={
 "crm":  {"dept":"crm","recipe":"do/report-page.md","bot":"crm-report","dir":E/"crm/live/reports","label":"CRM report","what":"Leads 24h and 7d by source and segment, pool, opportunities, calls, fixes for Jilan"},
 "sales":{"dept":"sales","recipe":"do/daily-pulse.md","bot":"sales-report","dir":E/"brain/live","pattern":"pulse.md","label":"Sales pulse","what":"Yesterday's leads, touches, opps, stage moves (writes brain/live/pulse.md)"},
 "marketing":{"dept":"marketing","recipe":"do/production-director.md","bot":"marketing-report","dir":E/"marketing-brain/live/production","label":"Production orders","what":"Videographer work orders and the social media buyer plan"},
 "publisher":{"dept":"marketing","recipe":"do/publisher.md","bot":"marketing-publisher","dir":E/"marketing-brain/live/posts","pattern":"P-*.md","label":"LinkedIn posts","what":"Drafts finished LinkedIn posts from selected ideas into the publish queue below"},
 "voice":{"dept":"voice","recipe":"do/call-queue.md","bot":"voice-report","dir":E/"voice/live/calls","label":"Call queue","what":"Today's call list and briefs (shadow mode until the voice key and standing yes exist)"},
}
# only departments registered in departments.json get a button (run-ondemand.sh would otherwise fall back to the centre folder)
_REG={d["id"] for d in json.loads((HQ/"departments.json").read_text())["departments"]}
JOBS={k:v for k,v in JOBS.items() if v["dept"] in _REG}
RUNNING={}
LOCK=threading.Lock()
def status():
    try: return json.loads((HQ/"status.json").read_text())
    except Exception: return {}
def latest(d,pattern="*.md"):
    if not d.exists(): return []
    fs=[p for p in d.glob(pattern) if p.is_file() and p.name!=".keep"]
    return sorted(fs,key=lambda p:p.stat().st_mtime,reverse=True)
def md2html(t):
    out=[]; lines=t.splitlines(); i=0; inlist=False; incode=False
    def inline(s):
        s=html.escape(s)
        s=re.sub(r"\*\*(.+?)\*\*",r"<b>\1</b>",s); s=re.sub(r"`(.+?)`",r"<code>\1</code>",s)
        s=re.sub(r"<< ?fill:?(.*?)>>",r'<span class="blank">fill:\1</span>',s)
        return s
    while i<len(lines):
        l=lines[i]
        if l.startswith("```"):
            incode=not incode; out.append("<pre>" if incode else "</pre>"); i+=1; continue
        if incode: out.append(html.escape(l)); i+=1; continue
        if l.startswith("|") and i+1<len(lines) and re.match(r"^\|\s*:?-",lines[i+1]):
            hdr=[c.strip() for c in l.strip().strip("|").split("|")]; i+=2; rows=[]
            while i<len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i+=1
            out.append("<table><thead><tr>"+"".join(f"<th>{inline(c)}</th>" for c in hdr)+"</tr></thead><tbody>"+"".join("<tr>"+"".join(f"<td>{inline(c)}</td>" for c in r)+"</tr>" for r in rows)+"</tbody></table>"); continue
        m=re.match(r"^(#{1,4})\s+(.*)",l)
        if m:
            if inlist: out.append("</ul>"); inlist=False
            n=len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); i+=1; continue
        if re.match(r"^\s*[-*]\s+",l) or re.match(r"^\s*\d+[.)]\s+",l):
            if not inlist: out.append("<ul>"); inlist=True
            out.append("<li>"+inline(re.sub(r"^\s*([-*]|\d+[.)])\s+","",l))+"</li>"); i+=1; continue
        if inlist: out.append("</ul>"); inlist=False
        if l.strip()=="---": out.append("<hr>")
        elif l.strip(): out.append(f"<p>{inline(l)}</p>")
        i+=1
    if inlist: out.append("</ul>")
    return "\n".join(out)
CSS="""
:root{--bg:#0b0a12;--panel:#15131f;--ink:#ece8f5;--mute:#9a94ad;--line:#2a2638;--gold:#e8c168;--ok:#7bd3a0;--run:#7dd3fc;--bad:#f06c6c}
@media(prefers-color-scheme:light){:root{--bg:#f6f4fb;--panel:#fff;--ink:#17141f;--mute:#5d586b;--line:#e2ddef;--gold:#9a6d00}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"IBM Plex Sans",Helvetica,Arial,sans-serif}
header{display:flex;align-items:center;gap:14px;padding:16px 24px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg)}
header h1{font-size:18px;margin:0;font-weight:600}header .tag{color:var(--gold);font-size:12px;letter-spacing:.12em;text-transform:uppercase}
header a{color:var(--mute);text-decoration:none;margin-left:14px}header a:first-of-type{margin-left:auto}main{max-width:1100px;margin:0 auto;padding:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px}
.card h2{margin:0 0 4px;font-size:16px}.card .what{color:var(--mute);font-size:13px;min-height:40px}
button{background:var(--gold);color:#17141f;border:0;border-radius:8px;padding:10px 14px;font-weight:600;cursor:pointer;font-size:14px;margin-top:10px}
button:disabled{opacity:.5;cursor:wait}.state{font-size:12px;margin-top:8px;color:var(--mute)}.state.run{color:var(--run)}.state.ok{color:var(--ok)}.state.bad{color:var(--bad)}
ul.files{list-style:none;padding:0;margin:8px 0 0}ul.files li{font-size:13px;margin:3px 0}ul.files a{color:var(--ink)}ul.files span{color:var(--mute);font-size:12px;margin-left:6px}
article{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:28px 32px;max-width:900px;margin:0 auto}
article h1{font-size:22px;margin-top:0}article h2{font-size:16px;margin:22px 0 8px;color:var(--gold);letter-spacing:.04em;text-transform:uppercase}
table{border-collapse:collapse;width:100%;margin:8px 0 14px;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{color:var(--mute);font-weight:600;font-size:12px;text-transform:uppercase}
.blank{background:#f0c14b33;color:var(--gold);padding:0 4px;border-radius:4px}pre{background:var(--bg);padding:12px;border-radius:8px;overflow:auto;font-size:13px}code{font-size:13px}
.post pre.posttext{white-space:pre-wrap;font:14px/1.5 -apple-system,"IBM Plex Sans",Helvetica,Arial,sans-serif;background:var(--bg);padding:12px;border-radius:8px;max-height:320px;overflow:auto}.post .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}button.ghost{background:transparent;color:var(--mute);border:1px solid var(--line)}
.tile{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--c,var(--gold));border-radius:10px;padding:16px 18px;margin-bottom:16px}
.tile.centre{border-top-color:var(--gold)}.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}.board .tile{margin:0}
.th{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.th h2{margin:0;font-size:17px}.next{color:var(--mute);font-size:12px;margin-left:auto}
.pill{font-size:11px;letter-spacing:.06em;text-transform:uppercase;padding:2px 8px;border-radius:999px;border:1px solid var(--line);color:var(--mute)}.pill.ok{color:var(--ok);border-color:var(--ok)}.pill.run{color:var(--run);border-color:var(--run)}.pill.bad{color:var(--bad);border-color:var(--bad)}
.head{margin:10px 0 8px;font-size:14px;line-height:1.45}.meta,.row{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin:6px 0;font-size:12px}
.lab{color:var(--mute);min-width:62px;text-transform:uppercase;letter-spacing:.06em;font-size:11px}
.chip{display:inline-block;padding:3px 9px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none;font-size:12px}.chip:hover{border-color:var(--gold)}.chip.strong{border-color:var(--c,var(--gold));font-weight:600}.chip.dim,.dim{color:var(--mute)}
a.chip+a.chip{margin-left:-2px}.dec{color:var(--gold);font-weight:600}.dec.none{color:var(--mute);font-weight:400}
.jobs .job{display:inline-flex;flex-direction:column;margin-right:10px}.jobs button{margin-top:6px;padding:7px 11px;font-size:13px}.jobs .state{font-size:11px}
h2.sec{margin:28px 0 6px;font-size:17px}
@media(max-width:600px){main{padding:16px}article{padding:18px}}
"""
PRINT="""
@page{size:A4;margin:14mm 14mm 16mm}
@media print{:root{--bg:#fff;--panel:#fff;--ink:#141414;--mute:#555;--line:#d9d9d9;--gold:#8a6100}
 body{background:#fff;font-size:11.5pt}header,.toolbar{display:none}main{padding:0;max-width:none}
 article{border:0;padding:0;max-width:none;border-radius:0}article h2{page-break-after:avoid}table{page-break-inside:auto}tr{page-break-inside:avoid}pre{white-space:pre-wrap}}
.toolbar{max-width:900px;margin:0 auto 12px;display:flex;gap:10px;align-items:center}.toolbar a.btn{background:var(--gold);color:#17141f;border-radius:8px;padding:8px 12px;font-weight:600;text-decoration:none;font-size:14px}.toolbar span{color:var(--mute);font-size:13px}
"""
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PDFDIR=E/"moonshelter/live/pdf"   # Kamel's desk; never inside a department folder (brain/ is written by sales only)
def make_pdf(job,f):
    """Print the rendered report to PDF with Chrome headless; the file lands next to the .md (same name, .pdf).
    No --user-data-dir: with one, Chrome 154 writes the PDF but never exits. A PDF newer than the .md is reused."""
    src=JOBS[job]["dir"]/f; PDFDIR.mkdir(parents=True,exist_ok=True); out=PDFDIR/f"{job}-{src.stem}.pdf"
    if out.exists() and out.stat().st_mtime>=src.stat().st_mtime: return out
    url=f"http://127.0.0.1:{PORT}/report?job={job}&f={urllib.parse.quote(f)}&print=1"
    try:
        subprocess.run([CHROME,"--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check","--no-pdf-header-footer",
                        f"--print-to-pdf={out}",url],timeout=60,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired: pass
    return out if out.exists() else None
def page(body,title="Moon Shelter"):
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}{PRINT}</style></head>
<body><header><span class="tag">Moon Shelter</span><h1>Board</h1><a href="/">board</a><a href="/graph">3D map</a><a href="/marketing">Marketing studio</a></header><main>{body}</main></body></html>"""
def state_of(job):
    b=status().get(JOBS[job]["bot"],{}); running=RUNNING.get(job) and RUNNING[job].poll() is None
    if running: return "run","running since "+b.get("started","now")+" · about 5 to 10 minutes"
    if not b: return "","never run"
    if b.get("state")=="failed": return "bad","failed "+b.get("finished","")+" · "+b.get("note","")
    return "ok","last run "+b.get("finished","")
QUEUE=E/"marketing-brain/live/publish-queue.md"; POSTS=E/"marketing-brain/live/posts"
QCOLS=["date","id","idea","channel","status","file","approved","posted","url"]
def read_queue():
    rows=[]
    if not QUEUE.exists(): return [],[]
    lines=QUEUE.read_text().splitlines()
    for i,l in enumerate(lines):
        if l.startswith("|") and not l.startswith("| date") and not re.match(r"^\|\s*-",l):
            c=[x.strip() for x in l.strip().strip("|").split("|")]
            if len(c)>=5 and re.match(r"^P-\d+$",c[1]): rows.append((i,dict(zip(QCOLS,c+[""]*(len(QCOLS)-len(c))))))
    return lines,rows
def post_text(pid):
    f=POSTS/f"{pid}.md"
    if not f.exists(): return ""
    t=f.read_text(errors="ignore"); m=re.search(r"^## Post\s*\n(.*?)(?=^## |\Z)",t,re.S|re.M)
    return (m.group(1) if m else "").strip()
def set_status(pid,status,url=""):
    lines,rows=read_queue(); now=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for i,r in rows:
        if r["id"]==pid:
            r["status"]=status
            if status=="APPROVED": r["approved"]=now
            if status=="POSTED": r["posted"]=now; r["url"]=url or r.get("url","")
            lines[i]="| "+" | ".join(r.get(k,"") for k in QCOLS)+" |"; QUEUE.write_text("\n".join(lines)+"\n")
            f=POSTS/f"{pid}.md"
            if f.exists():
                t=f.read_text(errors="ignore"); t=re.sub(r"^- status:.*$",f"- status: {status}",t,count=1,flags=re.M)
                if status=="APPROVED": t=re.sub(r"^- approved:.*$",f"- approved: {now}",t,count=1,flags=re.M)
                if status=="POSTED":
                    t=re.sub(r"^- posted:.*$",f"- posted: {now}",t,count=1,flags=re.M)
                    if url: t=re.sub(r"^- url:.*$",f"- url: {url}",t,count=1,flags=re.M)
                f.write_text(t)
            subprocess.Popen(["/bin/zsh","-c",f"git add -A && git commit -q -m 'publisher: {pid} {status} by Kamel {now}'"],cwd=E/"marketing-brain",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return True
    return False
def queue_html():
    _,rows=read_queue(); live=[r for _,r in rows if r["status"] in ("READY","APPROVED")]
    done=[r for _,r in rows if r["status"] in ("POSTED","REJECTED")][-5:]
    if not rows: return '<p style="color:var(--mute)">No posts drafted yet. Press "Generate linkedin posts" above.</p>'
    out=[]
    for r in live:
        txt=post_text(r["id"]); pid=r["id"]; appr=(" · approved "+r["approved"]) if r["approved"] else ""
        if r["status"]=="READY": btn='<button onclick="act(\'%s\',\'approve\')">Approve and open LinkedIn</button>'%pid
        else: btn='<button onclick="act(\'%s\',\'approve\')">Open LinkedIn again</button> <button onclick="posted(\'%s\')">Mark posted</button>'%(pid,pid)
        body=html.escape(txt) if txt else "(post text missing: "+html.escape(r["file"])+")"
        car=POSTS/f"{pid}-carousel.pdf"
        if car.exists(): body+='\n\n[ carousel: %s, attach it as a document when you post → <a href="/post-file?f=%s-carousel.pdf" style="color:var(--gold)">open PDF</a> ]'%(car.name,pid)
        out.append('<div class="card post" data-pid="%s"><h2>%s · %s</h2><div class="what">%s · %s%s</div><pre class="posttext">%s</pre><div class="row">%s <button class="ghost" onclick="act(\'%s\',\'reject\')">Reject</button> <span class="state">%d characters</span></div></div>'%(pid,pid,html.escape(r["idea"]),html.escape(r["channel"]),r["status"],html.escape(appr),body,btn,pid,len(txt)))
    if not live: out.append('<p style="color:var(--mute)">Nothing waiting for you.</p>')
    if done: out.append('<p style="color:var(--mute);font-size:13px">Recent: '+" · ".join(html.escape(f'{r["id"]} {r["status"].lower()} {r["posted"] or ""}') for r in done)+'</p>')
    return "".join(out)
# ---------- the flat board: one tile per department, every output one click away ----------
MAN=json.loads((HQ/"departments.json").read_text())
DEPTS=MAN["departments"]; CENTRE=MAN.get("centre",{"id":"moonshelter","name":"Moon Shelter","folder":"moonshelter"})
FOLDERS={d["id"]:E/d["folder"] for d in DEPTS}; FOLDERS[CENTRE["id"]]=E/CENTRE["folder"]
OUTPUTS={
 "crm":[("Sweeps","live/sweeps"),("Reports","live/reports"),("Scoreboard","live/scoreboard.md"),("Rules","ref/rules.md")],
 "sales":[("Pulse","live/pulse.md"),("Agent stats","live/agent-stats.md"),("Monday briefs","live/briefs"),("Leads daily","live/leads-daily"),("Actions","live/actions.md"),("Week","live/week.md"),("Team","ref/team.md")],
 "marketing":[("Production orders","live/production"),("Posts","live/posts"),("Plans","live/plans"),("Ideas","live/ideas.md"),("Week","live/week.md"),("Publish queue","live/publish-queue.md"),("Actions","live/actions.md")],
 "voice":[("Calls","live/calls"),("Rules","ref/rules.md"),("Scripts","ref/scripts.md")],
 "moonshelter":[("Digest","live/today.md"),("Decisions","live/decisions.md"),("Inbox","live/inbox"),("PDFs","live/pdf")],
}
def next_run(sched):
    """Next scheduled run as 'Tue 06:30 · label'. departments.json weekdays: 0=Sun … 6=Sat."""
    now=datetime.datetime.now(); best=None
    for s in sched or []:
        for k in range(0,8):
            d=(now+datetime.timedelta(days=k)).replace(hour=s["hour"],minute=s["minute"],second=0,microsecond=0)
            if ((d.weekday()+1)%7) in s["days"] and d>now and (best is None or d<best[0]): best=(d,s["label"])
    return f"{best[0]:%a %H:%M} · {best[1]}" if best else "on demand"
def section_lines(lines,name):
    out=[]; on=False
    for l in lines:
        if l.startswith("## "): on=l[3:].strip().lower().startswith(name.lower()); continue
        if on: out.append(l)
    return out
def report_info(folder):
    p=folder/"live/report.md"
    if not p.exists(): return None
    lines=p.read_text(errors="ignore").splitlines()
    m=re.search(r"(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?)",lines[0]) if lines else None
    find=[l for l in section_lines(lines,"Three findings") if re.match(r"^\s*\d+[.)]",l)]
    first=re.sub(r"\*\*|`","",re.sub(r"^\s*\d+[.)]\s*","",find[0])) if find else ""
    dec=[l for l in section_lines(lines,"Needs a decision") if re.match(r"^\s*\d+[.)]",l)]
    st=next((l[3:].replace("Status:","").strip() for l in lines if l.startswith("## Status")),"")
    return {"date":m.group(1) if m else "","first":first,"decisions":len(dec),"status":st}
def digest_info():
    p=FOLDERS[CENTRE["id"]]/"live/today.md"
    if not p.exists(): return {"date":"","line":""}
    lines=p.read_text(errors="ignore").splitlines(); date=""; line=""
    for i,l in enumerate(lines):
        if not date and re.match(r"^## \d{4}-\d{2}-\d{2}",l): date=l[3:].strip()
        if date and l.startswith("### In one line"):
            line=next((x for x in lines[i+1:] if x.strip()),""); break
    return {"date":date,"line":re.sub(r"\*\*|`","",line)}
def open_decisions():
    p=FOLDERS[CENTRE["id"]]/"live/decisions.md"
    return sum(1 for l in p.read_text(errors="ignore").splitlines() if re.match(r"^\d{4}-",l) and l.rstrip().endswith("| NEW")) if p.exists() else 0
def flink(dept,rel,label=None,cls=""):
    return '<a class="%s" href="/file?dept=%s&path=%s">%s</a>'%(cls,dept,urllib.parse.quote(rel),html.escape(label or rel))
def lslink(dept,rel,label):
    return '<a class="chip" href="/ls?dept=%s&path=%s">%s</a>'%(dept,urllib.parse.quote(rel),html.escape(label))
def safe_path(dept,rel):
    base=FOLDERS.get(dept)
    if not base or not rel or rel.startswith("/") or ".." in rel.split("/"): return None
    p=(base/rel)
    try: p.resolve().relative_to(base.resolve())
    except ValueError: return None
    return p
def pill(dept):
    cls,txt=("","never run")
    b=status().get(dept,{})
    if b:
        if b.get("state")=="running": cls,txt="run","running since "+b.get("started","")
        elif b.get("state")=="failed": cls,txt="bad","failed "+b.get("finished","")
        else: cls,txt="ok","last run "+b.get("finished","")
    return '<span class="pill %s">%s</span>'%(cls,html.escape(txt))
def outputs_html(dept):
    base=FOLDERS[dept]; chips=[]
    for label,rel in OUTPUTS.get(dept,[]):
        p=base/rel
        if p.is_dir():
            fs=latest(p,"*")
            fs=[f for f in fs if not f.name.startswith(".")]
            if fs: chips.append(flink(dept,str(fs[0].relative_to(base)),f"{label}: {fs[0].name}","chip")+lslink(dept,rel,"all"))
            else: chips.append('<span class="chip dim">%s: empty</span>'%html.escape(label))
        elif p.exists(): chips.append(flink(dept,rel,label,"chip"))
    return "".join(chips)
def jobs_html(dept):
    out=[]
    for k,j in JOBS.items():
        if j["dept"]!=dept: continue
        cls,txt=state_of(k)
        out.append('<div class="job" data-job="%s"><button onclick="run(\'%s\')" %s>Generate %s</button><div class="state %s">%s</div></div>'%(k,k,"disabled" if cls=="run" else "",html.escape(j["label"].lower()),cls,html.escape(txt)))
    return "".join(out)
def tile(d):
    dept=d["id"]; base=FOLDERS[dept]; r=report_info(base) or {"date":"","first":"","decisions":0,"status":""}
    hand=[]
    for f in sorted((base/"live/handoffs").glob("*.md")) if (base/"live/handoffs").exists() else []:
        first=(f.read_text(errors="ignore").splitlines() or [""])[0]; dt=first[:10] if re.match(r"^\d{4}-\d{2}-\d{2}",first) else ""
        hand.append(flink(dept,f"live/handoffs/{f.name}",f"to {f.stem} {dt}".strip(),"chip"))
    dec='<span class="dec">%d decision%s owed</span>'%(r["decisions"],"" if r["decisions"]==1 else "s") if r["decisions"] else '<span class="dec none">no decisions owed</span>'
    headline=html.escape(r["first"][:260]+("…" if len(r["first"])>260 else "")) if r["first"] else '<span class="dim">no report yet</span>'
    return f'''<section class="tile" style="--c:{d.get("color","#888")}">
<div class="th"><h2>{html.escape(d["name"])}</h2>{pill(dept)}<span class="next">next {html.escape(next_run(d.get("schedule")))}</span></div>
<p class="head">{headline}</p>
<div class="meta">{flink(dept,"live/report.md","report "+r["date"],"chip strong")}{dec}<span class="dim">{html.escape(r["status"][:90])}</span></div>
<div class="row"><span class="lab">handoffs</span>{"".join(hand) or '<span class="dim">none</span>'}</div>
<div class="row"><span class="lab">outputs</span>{outputs_html(dept)}</div>
<div class="row jobs">{jobs_html(dept)}</div>
</section>'''
def centre_tile():
    dg=digest_info(); n=open_decisions(); dept=CENTRE["id"]
    return f'''<section class="tile centre">
<div class="th"><h2>Moon Shelter</h2>{pill(dept)}<span class="next">digest {html.escape(dg["date"])} · next {html.escape(next_run(CENTRE.get("schedule")))}</span></div>
<p class="head">{html.escape(dg["line"]) or '<span class="dim">no digest yet</span>'}</p>
<div class="meta">{flink(dept,"live/today.md","full digest","chip strong")}{flink(dept,"live/decisions.md",f"{n} open decision{'s' if n!=1 else ''}","chip strong")}{outputs_html(dept)}</div>
</section>'''
JS_HOME="""<script>
async function act(pid,what){if(what==='reject'&&!confirm('Reject '+pid+'?'))return;let w=null;if(what==='approve')w=window.open('about:blank','_blank');
const r=await fetch('/queue/'+what+'/'+pid,{method:'POST'});const j=await r.json();if(!j.ok){if(w)w.close();alert(j.why||'failed');return}if(w){if(j.url)w.location=j.url;else w.close()}location.reload()}
async function posted(pid){const u=prompt('Posted. Paste the post URL if you have it (optional):','')||'';await fetch('/queue/posted/'+pid,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:u})});location.reload()}
async function run(k){const c=document.querySelector('[data-job="'+k+'"]');const b=c.querySelector('button');b.disabled=true;c.querySelector('.state').textContent='starting…';await fetch('/run/'+k,{method:'POST'});poll()}
async function poll(){const s=await (await fetch('/status')).json();let any=false;for(const k in s){const c=document.querySelector('[data-job="'+k+'"]');if(!c)continue;const st=c.querySelector('.state');st.className='state '+s[k][0];st.textContent=s[k][1];c.querySelector('button').disabled=s[k][0]==='run';if(s[k][0]==='run')any=true}
if(any)setTimeout(poll,8000);else if(window._wasRunning)location.reload();window._wasRunning=any}
poll();
</script>"""
def home():
    tiles="".join(tile(d) for d in DEPTS)
    body=(centre_tile()+'<div class="board">'+tiles+'</div>'
          +'<h2 class="sec" id="publishing">Publish queue · LinkedIn</h2><p class="dim" style="margin:0 0 12px;font-size:13px">Nothing goes out on its own. Approve opens your LinkedIn composer in a new tab with the text filled in, on this Mac or on the iPad; you press Post there, then mark it posted here.</p>'
          +'<div class="grid">'+queue_html()+'</div>'
          +'<p class="dim" style="font-size:12px;margin-top:28px">Bots run on Claude headless and read Salesforce read-only. Nothing on this page sends, posts or changes anything by itself. <a href="/graph" style="color:var(--gold)">3D map</a></p>'
          +JS_HOME)
    return page(body)
def ls_page(dept,rel):
    base=FOLDERS[dept]; p=safe_path(dept,rel)
    if not p or not p.is_dir(): return page("<article><p>not found</p></article>","not found")
    fs=[f for f in latest(p,"*") if not f.name.startswith(".")]
    rows="".join('<li>%s<span>%s · %s</span></li>'%(flink(dept,str(f.relative_to(base)),f.name),datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d %b %H:%M"),"folder" if f.is_dir() else f"{f.stat().st_size//1024} KB") for f in fs)
    return page(f'<article><h1>{html.escape(dept)} / {html.escape(rel)}</h1><ul class="files">{rows or "<li>empty</li>"}</ul></article>',f"{dept} · {rel}")
def file_page(dept,rel,printing=False):
    p=safe_path(dept,rel)
    if not p or not p.exists(): return None
    if p.is_dir(): return ls_page(dept,rel)
    ext=p.suffix.lower()
    if ext==".md":
        bar="" if printing else f'<div class="toolbar"><a class="btn" href="/pdf?dept={dept}&path={urllib.parse.quote(rel)}">Download PDF</a><span>{html.escape(dept)} / {html.escape(rel)}</span></div>'
        return page(f"{bar}<article>{md2html(p.read_text(errors='ignore'))}</article>",f"{dept} · {p.name}")
    return ("raw",p)
# --- remote access over Tailscale (Kamel's own devices only) ---
import ipaddress, threading, socket
TS_CLI=["/Applications/Tailscale.app/Contents/MacOS/Tailscale","tailscale"]
TS_NET=ipaddress.ip_network("100.64.0.0/10")   # Tailscale addresses; nothing else is ever answered
def tailscale_ip():
    for c in TS_CLI:
        try:
            out=subprocess.run([c,"ip","-4"],capture_output=True,text=True,timeout=5).stdout.strip().split()
            for ip in out:
                if ipaddress.ip_address(ip) in TS_NET: return ip
        except Exception: continue
    return ""
def client_ok(ip):
    try:
        a=ipaddress.ip_address(ip.split("%")[0]); return a.is_loopback or a in TS_NET
    except ValueError: return False
def serve_tailscale():
    """Bind a second listener on the Tailscale address once Tailscale is up; keep trying so a login later needs no restart."""
    bound=""
    while True:
        ip=tailscale_ip()
        if ip and ip!=bound:
            try:
                s=http.server.ThreadingHTTPServer((ip,PORT),H); bound=ip
                print("also listening on http://%s:%d (Tailscale)"%(ip,PORT)); sys.stdout.flush()
                threading.Thread(target=s.serve_forever,daemon=True).start()
            except OSError as e: print("tailscale bind failed:",e); sys.stdout.flush()
        time.sleep(30)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,body,ctype="text/html; charset=utf-8",code=200):
        b=body.encode(); self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if not client_ok(self.client_address[0]): return self.send("forbidden","text/plain",403)
        u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
        if u.path=="/marketing":
            return self.send((HQ/"tools/marketing.html").read_text(encoding="utf-8"))
        if u.path=="/marketing-data":
            jobs={k:dict(zip(("state","message"),state_of(k))) for k in ("marketing","publisher") if k in JOBS}
            return self.send(json.dumps(marketing_snapshot(E,MAN,status(),[r for _,r in read_queue()[1]],jobs)),"application/json")
        if u.path=="/graph-status":
            return self.send(json.dumps(status()),"application/json")
        if u.path=="/graph":
            g=HQ/"private/index.html"
            return self.send(g.read_text(errors="ignore")) if g.exists() else self.send("graph not built","text/plain",404)
        if u.path=="/": return self.send(home())
        if u.path=="/status": return self.send(json.dumps({k:state_of(k) for k in JOBS}),"application/json")
        if u.path=="/file":
            dept=q.get("dept",[""])[0]; rel=q.get("path",[""])[0]
            if dept not in FOLDERS: return self.send("bad request","text/plain",400)
            res=file_page(dept,rel,printing=bool(q.get("print")))
            if res is None: return self.send("not found","text/plain",404)
            if isinstance(res,tuple):
                p=res[1]; ext=p.suffix.lower(); ct={".pdf":"application/pdf",".png":"image/png",".jpg":"image/jpeg",".html":"text/html; charset=utf-8",".csv":"text/plain; charset=utf-8",".json":"application/json"}.get(ext,"text/plain; charset=utf-8")
                b=p.read_bytes(); self.send_response(200); self.send_header("Content-Type",ct); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
            return self.send(res)
        if u.path=="/ls":
            dept=q.get("dept",[""])[0]; rel=q.get("path",[""])[0]
            if dept not in FOLDERS: return self.send("bad request","text/plain",400)
            return self.send(ls_page(dept,rel))
        if u.path=="/pdf" and q.get("dept"):
            dept=q.get("dept",[""])[0]; rel=q.get("path",[""])[0]; p=safe_path(dept,rel)
            if dept not in FOLDERS or not p or not p.exists() or p.suffix!=".md": return self.send("bad request","text/plain",400)
            PDFDIR.mkdir(parents=True,exist_ok=True); out=PDFDIR/f"{dept}-{p.stem}.pdf"
            if not (out.exists() and out.stat().st_mtime>=p.stat().st_mtime):
                url=f"http://127.0.0.1:{PORT}/file?dept={dept}&path={urllib.parse.quote(rel)}&print=1"
                try: subprocess.run([CHROME,"--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check","--no-pdf-header-footer",f"--print-to-pdf={out}",url],timeout=60,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                except subprocess.TimeoutExpired: pass
            if not out.exists(): return self.send("PDF failed","text/plain",500)
            b=out.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/pdf"); self.send_header("Content-Disposition",f'inline; filename="{out.name}"'); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path=="/report":
            job=q.get("job",[""])[0]; f=q.get("f",[""])[0]
            if job not in JOBS or "/" in f or ".." in f: return self.send("bad request","text/plain",400)
            p=JOBS[job]["dir"]/f
            if not p.exists(): return self.send("not found","text/plain",404)
            bar="" if q.get("print") else f'<div class="toolbar"><a class="btn" href="/pdf?job={job}&f={urllib.parse.quote(f)}">Download PDF</a><span>A4 · saved as moonshelter/live/pdf/{job}-{html.escape(pathlib.Path(f).stem)}.pdf</span></div>'
            return self.send(page(f"{bar}<article>{md2html(p.read_text(errors='ignore'))}</article>",f"{JOBS[job]['label']} · {f}"))
        if u.path=="/post-file":
            f=q.get("f",[""])[0]
            if not re.match(r"^P-\d+-(carousel\.pdf|slide-\d+\.png)$",f) or not (POSTS/f).exists(): return self.send("not found","text/plain",404)
            b=(POSTS/f).read_bytes(); self.send_response(200); self.send_header("Content-Type","application/pdf" if f.endswith(".pdf") else "image/png"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        if u.path=="/pdf":
            job=q.get("job",[""])[0]; f=q.get("f",[""])[0]
            if job not in JOBS or "/" in f or ".." in f or not (JOBS[job]["dir"]/f).exists(): return self.send("bad request","text/plain",400)
            out=make_pdf(job,f)
            if not out: return self.send("PDF failed: Chrome headless did not produce a file","text/plain",500)
            b=out.read_bytes(); self.send_response(200); self.send_header("Content-Type","application/pdf")
            self.send_header("Content-Disposition",f'inline; filename="{out.name}"'); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b); return
        return self.send("not found","text/plain",404)
    def do_POST(self):
        if not client_ok(self.client_address[0]): return self.send("forbidden","text/plain",403)
        if self.path.startswith("/queue/"):
            parts=self.path.split("/"); what=parts[2] if len(parts)>2 else ""; pid=parts[3] if len(parts)>3 else ""
            if not re.match(r"^P-\d+$",pid) or what not in ("approve","posted","reject"): return self.send(json.dumps({"ok":False,"why":"bad request"}),"application/json",400)
            n=int(self.headers.get("Content-Length") or 0); body=json.loads(self.rfile.read(n).decode() or "{}") if n else {}
            url=""
            if what=="approve":
                txt=post_text(pid)
                if not txt: return self.send(json.dumps({"ok":False,"why":"post text missing"}),"application/json")
                ok=set_status(pid,"APPROVED")
                # Kamel's explicit yes: the page opens HIS LinkedIn composer with the text in a new tab, on the Mac or the iPad, and he presses Post. This server never posts.
                url="https://www.linkedin.com/feed/?shareActive=true&text="+urllib.parse.quote(txt)
            elif what=="posted": ok=set_status(pid,"POSTED",str(body.get("url",""))[:300])
            else: ok=set_status(pid,"REJECTED")
            return self.send(json.dumps({"ok":ok,"url":url,"why":"" if ok else "id not in queue"}),"application/json")
        if self.path.startswith("/run/"):
            k=self.path[5:]
            if k not in JOBS: return self.send("unknown job","text/plain",404)
            with LOCK:
                if RUNNING.get(k) and RUNNING[k].poll() is None: return self.send(json.dumps({"ok":False,"why":"already running"}),"application/json")
                j=JOBS[k]; log=open(pathlib.Path.home()/f"Library/Logs/elysian-{j['dept']}.log","a")
                RUNNING[k]=subprocess.Popen(["/bin/zsh",str(HQ/"tools/run-ondemand.sh"),j["dept"],j["recipe"],j["bot"]],stdout=log,stderr=log,stdin=subprocess.DEVNULL)
            return self.send(json.dumps({"ok":True}),"application/json")
        return self.send("not found","text/plain",404)
if __name__=="__main__":
    http.server.ThreadingHTTPServer.allow_reuse_address=True
    try:
        srv=http.server.ThreadingHTTPServer(("127.0.0.1",PORT),H)
    except OSError as e:
        if e.errno==48: print("Moon Shelter reports is already running: open http://127.0.0.1:%d"%PORT); sys.exit(0)
        raise
    print("Moon Shelter reports on http://127.0.0.1:%d"%PORT); sys.stdout.flush()
    threading.Thread(target=serve_tailscale,daemon=True).start()
    srv.serve_forever()
