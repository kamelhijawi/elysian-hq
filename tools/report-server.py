#!/usr/bin/env python3
"""Moon Shelter reports page. Local only (127.0.0.1:8770). Press a button, a department bot runs its on-demand recipe
on Claude headless, and the report renders here as a web page. Nothing here is public; reports contain names."""
import http.server, json, pathlib, subprocess, threading, datetime, html, re, urllib.parse, sys
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
header a{color:var(--mute);text-decoration:none;margin-left:auto}main{max-width:1100px;margin:0 auto;padding:24px}
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
def page(body,title="Moon Shelter reports"):
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}{PRINT}</style></head>
<body><header><span class="tag">Moon Shelter</span><h1>Reports</h1><a href="/">all reports</a></header><main>{body}</main></body></html>"""
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
def home():
    cards=[]
    for k,j in JOBS.items():
        cls,txt=state_of(k); files=latest(j["dir"],j.get("pattern","*.md"))[:6]
        fl="".join(f'<li><a href="/report?job={k}&f={urllib.parse.quote(p.name)}">{html.escape(p.name)}</a><span>{datetime.datetime.fromtimestamp(p.stat().st_mtime):%d %b %H:%M}</span> <a href="/pdf?job={k}&f={urllib.parse.quote(p.name)}" style="color:var(--gold);font-size:12px">PDF</a></li>' for p in files)
        cards.append(f'''<div class="card" data-job="{k}"><h2>{j["label"]}</h2><div class="what">{j["what"]}</div>
<button onclick="run('{k}')" {"disabled" if cls=="run" else ""}>Generate {j["label"].lower()}</button><div class="state {cls}">{html.escape(txt)}</div><ul class="files">{fl or "<li><span>no reports yet</span></li>"}</ul></div>''')
    return page(f'''<p style="color:var(--mute);margin-top:0">Press a button. The department bot runs on Claude headless, reads Salesforce read-only, writes a dated file, and it appears here. Nothing is sent or changed anywhere.</p>
<div class="grid">{"".join(cards)}</div>
<h2 style="margin:28px 0 6px;font-size:17px">Publish queue · LinkedIn</h2>
<p style="color:var(--mute);margin:0 0 12px;font-size:13px">Nothing goes out on its own. Approve opens your LinkedIn composer in Chrome with the text filled in; you press Post there, then mark it posted here.</p>
<div class="grid">{queue_html()}</div>
<script>
async function act(pid,what){{if(what==='reject'&&!confirm('Reject '+pid+'?'))return;const r=await fetch('/queue/'+what+'/'+pid,{{method:'POST'}});const j=await r.json();if(!j.ok)alert(j.why||'failed');location.reload()}}
async function posted(pid){{const u=prompt('Posted. Paste the post URL if you have it (optional):','')||'';await fetch('/queue/posted/'+pid,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{url:u}})}});location.reload()}}
async function run(k){{const c=document.querySelector(`[data-job="${{k}}"]`);const b=c.querySelector('button');b.disabled=true;c.querySelector('.state').textContent='starting…';
await fetch('/run/'+k,{{method:'POST'}});poll()}}
async function poll(){{const s=await (await fetch('/status')).json();let any=false;for(const k in s){{const c=document.querySelector(`[data-job="${{k}}"]`);if(!c)continue;const st=c.querySelector('.state');st.className='state '+s[k][0];st.textContent=s[k][1];c.querySelector('button').disabled=s[k][0]==='run';if(s[k][0]==='run')any=true}}
if(any)setTimeout(poll,8000);else if(window._wasRunning)location.reload();window._wasRunning=any}}
poll();
</script>''')
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
    def send(self,body,ctype="text/html; charset=utf-8",code=200):
        b=body.encode(); self.send_response(code); self.send_header("Content-Type",ctype); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(u.query)
        if u.path=="/": return self.send(home())
        if u.path=="/status": return self.send(json.dumps({k:state_of(k) for k in JOBS}),"application/json")
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
        if self.path.startswith("/queue/"):
            parts=self.path.split("/"); what=parts[2] if len(parts)>2 else ""; pid=parts[3] if len(parts)>3 else ""
            if not re.match(r"^P-\d+$",pid) or what not in ("approve","posted","reject"): return self.send(json.dumps({"ok":False,"why":"bad request"}),"application/json",400)
            n=int(self.headers.get("Content-Length") or 0); body=json.loads(self.rfile.read(n).decode() or "{}") if n else {}
            if what=="approve":
                txt=post_text(pid)
                if not txt: return self.send(json.dumps({"ok":False,"why":"post text missing"}),"application/json")
                ok=set_status(pid,"APPROVED")
                # Kamel's explicit yes: open HIS LinkedIn composer with the text; he presses Post himself. This server never posts.
                subprocess.Popen(["open","-a","Google Chrome","https://www.linkedin.com/feed/?shareActive=true&text="+urllib.parse.quote(txt)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            elif what=="posted": ok=set_status(pid,"POSTED",str(body.get("url",""))[:300])
            else: ok=set_status(pid,"REJECTED")
            return self.send(json.dumps({"ok":ok,"why":"" if ok else "id not in queue"}),"application/json")
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
    srv.serve_forever()
