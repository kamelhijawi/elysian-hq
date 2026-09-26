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
@media(max-width:600px){main{padding:16px}article{padding:18px}}
"""
def page(body,title="Moon Shelter reports"):
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head>
<body><header><span class="tag">Moon Shelter</span><h1>Reports</h1><a href="/">all reports</a></header><main>{body}</main></body></html>"""
def state_of(job):
    b=status().get(JOBS[job]["bot"],{}); running=RUNNING.get(job) and RUNNING[job].poll() is None
    if running: return "run","running since "+b.get("started","now")+" · about 5 to 10 minutes"
    if not b: return "","never run"
    if b.get("state")=="failed": return "bad","failed "+b.get("finished","")+" · "+b.get("note","")
    return "ok","last run "+b.get("finished","")
def home():
    cards=[]
    for k,j in JOBS.items():
        cls,txt=state_of(k); files=latest(j["dir"],j.get("pattern","*.md"))[:6]
        fl="".join(f'<li><a href="/report?job={k}&f={urllib.parse.quote(p.name)}">{html.escape(p.name)}</a><span>{datetime.datetime.fromtimestamp(p.stat().st_mtime):%d %b %H:%M}</span></li>' for p in files)
        cards.append(f'''<div class="card" data-job="{k}"><h2>{j["label"]}</h2><div class="what">{j["what"]}</div>
<button onclick="run('{k}')" {"disabled" if cls=="run" else ""}>Generate {j["label"].lower()}</button><div class="state {cls}">{html.escape(txt)}</div><ul class="files">{fl or "<li><span>no reports yet</span></li>"}</ul></div>''')
    return page(f'''<p style="color:var(--mute);margin-top:0">Press a button. The department bot runs on Claude headless, reads Salesforce read-only, writes a dated file, and it appears here. Nothing is sent or changed anywhere.</p>
<div class="grid">{"".join(cards)}</div>
<script>
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
            return self.send(page(f"<article>{md2html(p.read_text(errors='ignore'))}</article>",f"{JOBS[job]['label']} · {f}"))
        return self.send("not found","text/plain",404)
    def do_POST(self):
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
    print("Moon Shelter reports on http://127.0.0.1:%d"%PORT); sys.stdout.flush()
    http.server.ThreadingHTTPServer(("127.0.0.1",PORT),H).serve_forever()
