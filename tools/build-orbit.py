#!/usr/bin/env python3
"""Knowledge graph of both departments: nodes + links from the files. Writes hq/graph.json and hq/index.html (3D force graph)."""
import re, json, pathlib, subprocess, datetime, html
HQ=pathlib.Path(__file__).resolve().parent.parent
B=HQ.parent/"brain"; M=HQ.parent/"marketing-brain"
nodes={}; links=[]
def add(id_,label,type_,group,size=4,meta=""):
    if id_ not in nodes: nodes[id_]={"id":id_,"label":label,"type":type_,"group":group,"size":size,"meta":meta}
    return id_
def link(a,b,rel):
    if a in nodes and b in nodes and a!=b: links.append({"source":a,"target":b,"rel":rel})
def cells(line): return [c.strip() for c in line.strip().strip("|").split("|")]
# centre + departments
add("orbit","Moon Shelter","HQ","hq",16,"Elysian HQ · the centre")
MAN=json.loads((HQ/"departments.json").read_text())
DAYS=["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
def sched_text(d):
    if not d.get("schedule"): return "on demand"
    return " · ".join(f"{s['label']} {'/'.join(DAYS[x] for x in s['days']) if len(s['days'])<5 else 'Mon–Fri'} {s['hour']:02d}:{s['minute']:02d}" for s in d["schedule"])
for d in MAN["departments"]:
    add(d["id"],d["name"],"Department",d["id"],12,f"{d['folder']}/ · {sched_text(d)}")
    link("orbit",d["id"],"owns")
    add(f"bot:{d['id']}",f"{d['name']} bot","Bot",d["id"],7,f"{d['engine']} · {sched_text(d)}"); link(d["id"],f"bot:{d['id']}","runs")
def files(root,dept,prefix):
    for layer in ("ref","live","do"):
        d=root/layer
        if not d.exists(): continue
        for p in sorted(d.glob("*.md")):
            fid=f"{prefix}:{layer}/{p.name}"; t={"ref":"Reference","live":"Live log","do":"Recipe"}[layer]
            txt=p.read_text(errors="ignore"); blanks=len(re.findall(r"<< ?fill",txt))
            add(fid,p.stem,t,dept,5 if layer!="do" else 6,f"{layer}/{p.name} · {blanks} blanks")
            link(dept,fid,layer)
        # recipes -> LOAD links
    for p in sorted((root/"do").glob("*.md")):
        txt=p.read_text(errors="ignore"); m=re.search(r"^LOAD:\s*(.+)$",txt,re.M)
        if not m: continue
        for item in re.split(r",\s*",m.group(1)):
            item=item.strip()
            if item.startswith("../brain/"):
                tgt="brain:"+item[len("../brain/"):]
            elif item.startswith("ref/") or item.startswith("live/") or item.startswith("do/"):
                if item.endswith("/*"):
                    for q in sorted((root/item[:-2]).glob("*.md")): link(f"{prefix}:do/{p.name}",f"{prefix}:{item[:-2]}/{q.name}","loads")
                    continue
                tgt=f"{prefix}:{item}"
            else: continue
            link(f"{prefix}:do/{p.name}",tgt,"loads")
files(B,"sales","brain"); files(M,"mkt-advisor","mkt")
for extra,prefix in (("crm","crm"),("people","people"),("advisory","advisory")):
    if (HQ.parent/extra).exists(): files(HQ.parent/extra,extra,prefix)
PREFIX={"brain":"brain","marketing-brain":"mkt","crm":"crm","people":"people","advisory":"advisory"}
for d in MAN["departments"]:
    pf=PREFIX[d["folder"]]
    for r in d.get("recipes",[]):            # recipes this department owns inside a shared folder
        rid=f"{pf}:{r}"
        if rid in nodes:
            nodes[rid]["group"]=d["id"]; link(d["id"],rid,"do")
    for sc in d.get("schedule",[]): link(f"bot:{d['id']}",f"{pf}:{sc['recipe']}","runs")
# team: agents + teams
team=(B/"ref/team.md").read_text(errors="ignore")
for l in team.splitlines():
    if l.startswith("| ") and not l.startswith("| Agent") and "Team 2 agents" not in l:
        c=cells(l)
        if len(c)<5 or c[0].startswith("<<"): continue
        name=c[0]; t=c[1] if not c[1].startswith("<<") else "Unassigned"
        tid=add(f"team:{t}",t,"Team","sales",7,"team")
        link("sales",tid,"team")
        aid=add(f"agent:{name}",name,"Agent","sales",2.5,c[4][:60])
        link(tid,aid,"member")
        if "Team Leader" in c[4] or "Sales Manager" in c[4]: link("brain:ref/team.md",aid,"lead")
link("brain:ref/team.md","team:Secondary","lists")
# developers: removed from the graph at Kamel's request (2026-09-17)
# ideas, plans, actions
ideas=(M/"live/ideas.md").read_text(errors="ignore") if (M/"live/ideas.md").exists() else ""
for l in ideas.splitlines():
    if l.startswith("2026-"):
        c=cells(l)
        if len(c)>=2:
            iid=add(f"idea:{c[1]}",c[1],"Idea","mkt-advisor",3.5,(c[2] if len(c)>2 else "")[:90]); link("mkt:live/ideas.md",iid,"holds"); link("mkt:do/creative-director.md",iid,"wrote")
for p in sorted((M/"live/plans").glob("*.md")):
    pid=add(f"plan:{p.stem}",p.stem,"Plan","mkt-advisor",6,"live/plans"); link("mkt:do/campaign-planner.md",pid,"wrote"); link("mkt:do/media-planner.md",pid,"wrote"); link("mkt:live/plans.md",pid,"lists")
for root,prefix,dept in ((B,"brain","sales"),(M,"mkt","mkt-advisor"),(HQ.parent/"crm","crm","crm"),(HQ.parent/"people","people","people"),(HQ.parent/"advisory","advisory","advisory")):
    a=root/"live/actions.md"
    if a.exists():
        for l in a.read_text(errors="ignore").splitlines():
            if l.startswith("2026-") and "| OPEN |" in l:
                c=cells(l); aid=add(f"act:{prefix}:{c[2][:50]}",c[2][:48],"Open action",dept,3,f"{c[1]} · due {c[3]}")
                link(f"{prefix}:live/actions.md",aid,"open")
                if c[1].startswith("Kamel"): link("orbit",aid,"owner")
# developers referenced by ideas/plans
if "plan:2026-09-12-launch-media-plan" in nodes: link("plan:2026-09-12-launch-media-plan","brain:ref/developers.md","reads")
# marketing reads sales
for l in links[:]:
    pass
def sh(c,cwd): 
    try: return subprocess.check_output(c,cwd=cwd,shell=True,text=True).strip()
    except Exception: return ""
status=json.loads((HQ/"status.json").read_text()) if (HQ/"status.json").exists() else {}
meta={"status":status,"departments":[{"id":d["id"],"name":d["name"],"color":d["color"],"schedule":d.get("schedule",[])} for d in MAN["departments"]],"built":datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),"sales_commits":sh("git rev-list --count HEAD",B),"mkt_commits":sh("git rev-list --count HEAD",M)}
G={"nodes":list(nodes.values()),"links":links,"meta":meta}
def publicize(G):
    """Public copy: no agent names, no developer contacts or commission, no action text."""
    import copy; P=copy.deepcopy(G); idmap={}; a=c=0
    for n in P["nodes"]:
        old=n["id"]
        if n["type"]=="Agent":
            a+=1; n["label"]=f"Agent {a:02d}"; n["meta"]=""; n["id"]=f"agent:{a:02d}"
        elif n["type"]=="Developer":
            n["meta"]="developer"
        elif n["type"]=="Open action":
            c+=1; due=(n.get("meta") or "").split("due ")[-1] if "due " in (n.get("meta") or "") else ""
            n["label"]=f"Action {c:02d}"; n["meta"]=(f"due {due}" if due and "fill" not in due else "open"); n["id"]=f"act:{c:02d}"
        elif n["type"]=="Team" and n["label"] not in ("Secondary","ELITE","UAE Nationals","Unassigned"):
            n["label"]="Team"
        elif n["type"]=="Idea":
            n["meta"]=""
        idmap[old]=n["id"]
    for l in P["links"]:
        l["source"]=idmap.get(l["source"],l["source"]); l["target"]=idmap.get(l["target"],l["target"])
    if "status" in P["meta"]:
        for b in P["meta"]["status"].values(): b["note"]=""
    return P
PUB=publicize(G)
(HQ/"graph.json").write_text(json.dumps(PUB),encoding="utf-8")
counts={}
for n in nodes.values(): counts[n["type"]]=counts.get(n["type"],0)+1
J=json.dumps(PUB)
J_PRIVATE=json.dumps(G)
page=r"""<title>Moon Shelter</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{--bg:#06090F;--ink:#EAF0F4;--ink2:#93A4B3;--dim:#56697A;--line:#1C2836;--teal:#39C9B6;--gold:#E0B45C}
*{box-sizing:border-box} html{color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 "IBM Plex Sans",system-ui,sans-serif;height:100vh;overflow:hidden}
#g{position:fixed;inset:0}
.ui{position:fixed;z-index:2;pointer-events:none}
.ui>*{pointer-events:auto}
.top{top:18px;left:22px;right:22px;display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.brand{font:500 11px "IBM Plex Mono",monospace;letter-spacing:.22em;text-transform:uppercase;color:var(--teal)}
h1{font:400 34px/1 "DM Serif Display",Georgia,serif;margin:4px 0 0;letter-spacing:-.01em}
h1 span{font:500 11px "IBM Plex Mono",monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);vertical-align:middle;margin-left:10px;border:1px solid rgba(224,180,92,.5);border-radius:999px;padding:3px 8px}
.sub{color:var(--ink2);font-size:12.5px;margin-top:6px}
.ctl{display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.btn,.seg button,input.q{font:500 12.5px "IBM Plex Sans",sans-serif;color:var(--ink);background:rgba(12,18,28,.8);border:1px solid var(--line);border-radius:9px;padding:8px 12px;backdrop-filter:blur(10px);cursor:pointer}
.btn:hover,.seg button:hover{border-color:#2E4256}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:9px;overflow:hidden;background:rgba(12,18,28,.8);backdrop-filter:blur(10px)}
.seg button{border:0;border-radius:0}.seg button.on{background:var(--teal);color:#04201C}
input.q{width:240px;cursor:text}input.q::placeholder{color:var(--dim)}
.legend{left:22px;bottom:22px;width:250px;max-height:52vh;overflow:auto;background:rgba(12,18,28,.82);border:1px solid var(--line);border-radius:12px;padding:12px 14px;backdrop-filter:blur(10px)}
.legend .h{font:500 11px "IBM Plex Mono",monospace;letter-spacing:.16em;text-transform:uppercase;color:var(--ink2);margin-bottom:8px}
.legend .row{display:flex;justify-content:space-between;align-items:center;padding:4px 0;cursor:pointer;font-size:13px}
.legend .row.off{opacity:.35}
.legend .row i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:9px;vertical-align:-1px}
.legend .row b{font:500 12px "IBM Plex Mono",monospace;color:var(--ink2)}
.legend .tog{display:flex;justify-content:space-between;align-items:center;margin-top:10px;padding-top:10px;border-top:1px solid var(--line);font-size:12.5px}
.sw{width:36px;height:20px;border-radius:999px;background:var(--teal);position:relative;cursor:pointer}
.sw:after{content:"";position:absolute;top:3px;right:3px;width:14px;height:14px;border-radius:50%;background:#04201C}
.sw.off{background:#2A3A4C}.sw.off:after{right:auto;left:3px;background:#93A4B3}
.status{right:22px;bottom:22px;font:400 12px "IBM Plex Mono",monospace;color:var(--dim);text-align:right}
.status a{color:var(--teal);text-decoration:none}
.tip{position:fixed;z-index:3;pointer-events:none;display:none;background:rgba(10,16,26,.95);border:1px solid var(--line);border-radius:10px;padding:10px 12px;max-width:280px;font-size:12.5px;backdrop-filter:blur(10px)}
.tip .n{font-weight:600;font-size:14px}.tip .t{color:var(--gold);font:500 11px "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase;margin:2px 0 6px}
.tip .m{color:var(--ink2)}.tip .c{color:var(--dim);margin-top:6px;font-size:11.5px}
.focus{position:fixed;z-index:2;right:22px;top:92px;width:290px;display:none;background:rgba(12,18,28,.86);border:1px solid var(--line);border-radius:12px;padding:14px 16px;backdrop-filter:blur(10px)}
.focus .n{font:400 20px "DM Serif Display",Georgia,serif}.focus .t{color:var(--gold);font:500 11px "IBM Plex Mono",monospace;letter-spacing:.1em;text-transform:uppercase}
.focus ul{margin:8px 0 0;padding:0;list-style:none;max-height:40vh;overflow:auto}.focus li{padding:4px 0;border-top:1px solid var(--line);font-size:12.5px;cursor:pointer}.focus li b{color:var(--ink2);font-weight:400;font-family:"IBM Plex Mono",monospace;font-size:11px}
.focus .x{float:right;cursor:pointer;color:var(--ink2)}
</style>
<div id="g"></div>
<div class="ui top">
  <div><div class="brand">Elysian · HQ</div><h1>Moon Shelter <span>live</span></h1><div class="sub" id="sub"></div><div class="sub" id="bots" style="margin-top:8px"></div></div>
  <div class="ctl">
    <input class="q" id="q" placeholder="Search nodes… agent, developer, file, idea">
    <div class="seg"><button id="b3" class="on">3D</button><button id="b2">2D</button></div>
    <button class="btn" id="rot">Pause orbit</button>
    <button class="btn" id="fit">Fit</button>
  </div>
</div>
<div class="ui legend"><div class="h">Entities</div><div id="leg"></div><div class="tog"><span>Show labels</span><div class="sw" id="lab"></div></div></div>
<div class="ui status" id="st"></div>
<div class="tip" id="tip"></div>
<div class="focus" id="focus"></div>
<script src="https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three-spritetext@1.8.2/dist/three-spritetext.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/force-graph@1.43.5/dist/force-graph.min.js"></script>
<script>
const G=__DATA__;
const COL={"HQ":"#FFF1C7","Department":"#E0B45C","Bot":"#7BD3A0","Recipe":"#39C9B6","Reference":"#5DA9E9","Live log":"#B58CF6","Agent":"#F27FA5","Team":"#F2A65A","Idea":"#C9A8FF","Plan":"#5EE6D0","Open action":"#9AA9B3"};
const DEPTS=G.meta.departments||[];const DCOL=Object.fromEntries(DEPTS.map(d=>[d.id,d.color]));
G.nodes.forEach(n=>{if(n.id==='orbit'){n.fx=0;n.fy=0;n.fz=0}const i=DEPTS.findIndex(d=>d.id===n.id);if(i>=0){const a=i/DEPTS.length*Math.PI*2-Math.PI/2;n.fx=Math.cos(a)*190;n.fy=Math.sin(a)*190;n.fz=0}});
const byId=Object.fromEntries(G.nodes.map(n=>[n.id,n]));
const deg={};G.links.forEach(l=>{deg[l.source]=(deg[l.source]||0)+1;deg[l.target]=(deg[l.target]||0)+1});
const counts={};G.nodes.forEach(n=>counts[n.type]=(counts[n.type]||0)+1);
const ST=G.meta.status||{};function botState(k){const b=ST[k];if(!b)return{s:'never run',c:'#56697A'};if(b.state==='running')return{s:'running since '+b.started,c:'#E0B45C'};if(b.state==='failed')return{s:'failed '+b.finished+' · '+(b.note||''),c:'#F06C6C'};const h=(Date.now()-new Date(b.finished.replace(' ','T')).getTime())/36e5;return{s:(h<24?'active · ':'idle · ')+'last ok '+b.finished+' · '+(b.note||''),c:h<24?'#7BD3A0':'#93A4B3'}}
const BOT={};DEPTS.forEach(d=>{BOT[d.id]=d.id;BOT['bot:'+d.id]=d.id});
function nextRun(d){if(!d.schedule.length)return 'on demand';const now=new Date();let best=null;d.schedule.forEach(s=>s.days.forEach(wd=>{for(let k=0;k<8;k++){const t=new Date(now);t.setDate(now.getDate()+k);t.setHours(s.hour,s.minute,0,0);if(t.getDay()===wd&&t>now){if(!best||t<best.t)best={t,label:s.label};break}}}));return best?`next ${best.label} ${best.t.toLocaleString('en-GB',{weekday:'short',hour:'2-digit',minute:'2-digit'})}`:''}
G.nodes.forEach(n=>{if(BOT[n.id]){const st=botState(BOT[n.id]);n.meta=(n.meta?n.meta+' · ':'')+st.s;n.stateColor=st.c}});
const hidden=new Set();let labels=true,mode='3d',rotating=true,query='';
document.getElementById('sub').textContent=`${G.nodes.length} nodes · ${G.links.length} links · built ${G.meta.built}`;
document.getElementById('bots').innerHTML=DEPTS.map(d=>{const st=botState(d.id);return `<div style="margin-top:3px"><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${st.c};box-shadow:0 0 8px ${st.c};margin-right:8px"></i><b style="color:${d.color}">${d.name}</b> <span style="color:var(--ink2)">${st.s} · ${nextRun(d)}</span></div>`}).join('');
const leg=document.getElementById('leg');
Object.entries(counts).sort((a,b)=>b[1]-a[1]).forEach(([t,c])=>{const r=document.createElement('div');r.className='row';r.innerHTML=`<span><i style="background:${COL[t]}"></i>${t}</span><b>${c}</b>`;r.onclick=()=>{hidden.has(t)?hidden.delete(t):hidden.add(t);r.classList.toggle('off');redraw()};leg.appendChild(r)});
function visible(){const ns=G.nodes.filter(n=>!hidden.has(n.type)&&(!query||n.label.toLowerCase().includes(query)||n.type.toLowerCase().includes(query)));const ids=new Set(ns.map(n=>n.id));const ls=G.links.filter(l=>ids.has(typeof l.source==='object'?l.source.id:l.source)&&ids.has(typeof l.target==='object'?l.target.id:l.target)).map(l=>({source:typeof l.source==='object'?l.source.id:l.source,target:typeof l.target==='object'?l.target.id:l.target,rel:l.rel}));return {nodes:ns.map(n=>({...n})),links:ls}}
const tip=document.getElementById('tip'),focus=document.getElementById('focus');
function topLinks(n,k){return G.links.filter(l=>(l.source.id||l.source)===n.id||(l.target.id||l.target)===n.id).slice(0,k).map(l=>{const o=(l.source.id||l.source)===n.id?(l.target.id||l.target):(l.source.id||l.source);return `<span style="color:var(--dim)">${l.rel}</span> ${byId[o]?byId[o].label:o}`})}
function showTip(n,x,y){if(!n){tip.style.display='none';return}tip.style.display='block';tip.style.left=(x+18)+'px';tip.style.top=(y+18)+'px';const extra='';tip.innerHTML=`<div class="n">${n.label}</div><div class="t">${n.type}</div>${extra}<div class="m">${n.meta||''}</div><div class="c">${deg[n.id]||0} connections<br>${topLinks(n,4).join('<br>')}</div><div class="c">click to focus</div>`}
function showFocus(n){if(!n){focus.style.display='none';return}const nb=G.links.filter(l=>(l.source.id||l.source)===n.id||(l.target.id||l.target)===n.id).map(l=>{const o=(l.source.id||l.source)===n.id?(l.target.id||l.target):(l.source.id||l.source);return {o:byId[o],rel:l.rel}}).filter(x=>x.o);focus.style.display='block';focus.innerHTML=`<span class="x" onclick="this.parentNode.style.display='none'">✕</span><div class="t">${n.type}</div><div class="n">${n.label}</div><div style="color:var(--ink2);font-size:12px;margin-top:4px">${n.meta||''}</div><ul>${nb.map(x=>`<li data-id="${x.o.id}"><b>${x.rel} ·</b> ${x.o.label} <b style="float:right">${x.o.type}</b></li>`).join('')}</ul>`;focus.querySelectorAll('li').forEach(li=>li.onclick=()=>focusNode(byId[li.dataset.id]))}
let g3,g2;const el=document.getElementById('g');
function nodeSize(n){return Math.max(2,n.size*(0.9+Math.min(deg[n.id]||0,12)/12))}
const glowTex=(()=>{const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');const g=x.createRadialGradient(64,64,0,64,64,64);g.addColorStop(0,'rgba(255,255,255,.9)');g.addColorStop(.25,'rgba(255,255,255,.35)');g.addColorStop(1,'rgba(255,255,255,0)');x.fillStyle=g;x.fillRect(0,0,128,128);return new THREE.CanvasTexture(c)})();
function nodeObj(n){const r=nodeSize(n)*(n.type==='Agent'?0.55:0.8);const col=new THREE.Color(n.type==='Department'&&DCOL[n.id]?DCOL[n.id]:COL[n.type]);const grp=new THREE.Group();
 const seg=n.type==='Agent'?12:24;const mat=new THREE.MeshPhongMaterial({color:col,emissive:col,emissiveIntensity:n.type==='HQ'?.9:n.type==='Department'?.6:.35,shininess:60,specular:0x334455});
 grp.add(new THREE.Mesh(new THREE.SphereGeometry(r,seg,seg),mat));
 const glow=new THREE.Sprite(new THREE.SpriteMaterial({map:glowTex,color:(n.type==='Bot'&&n.stateColor)?new THREE.Color(n.stateColor):col,transparent:true,opacity:n.type==='HQ'?.9:n.type==='Department'?.7:n.type==='Agent'?.25:.45,depthWrite:false,blending:THREE.AdditiveBlending}));const gs=r*(n.type==='HQ'?7:n.type==='Department'?5.5:3.2);glow.scale.set(gs,gs,1);grp.add(glow);
 if(labels&&!(n.type==='Agent'&&(deg[n.id]||0)<2&&!query)){const t=new SpriteText(n.label);t.color=COL[n.type];t.textHeight=n.type==='HQ'?7:n.type==='Department'?5.2:n.type==='Agent'?2.2:3.2;t.fontFace='IBM Plex Sans';t.backgroundColor='rgba(6,9,15,.55)';t.padding=1.2;t.borderRadius=2;t.position.y=r*1.6+2;grp.add(t)}
 return grp}
function addStars(scene){const n=2200,pos=new Float32Array(n*3),colr=new Float32Array(n*3);for(let i=0;i<n;i++){const R=900+Math.random()*900,th=Math.random()*Math.PI*2,ph=Math.acos(2*Math.random()-1);pos[i*3]=R*Math.sin(ph)*Math.cos(th);pos[i*3+1]=R*Math.sin(ph)*Math.sin(th);pos[i*3+2]=R*Math.cos(ph);const c=Math.random()>.9?new THREE.Color('#E0B45C'):Math.random()>.85?new THREE.Color('#39C9B6'):new THREE.Color('#C8DDE8');colr[i*3]=c.r;colr[i*3+1]=c.g;colr[i*3+2]=c.b}
 const geo=new THREE.BufferGeometry();geo.setAttribute('position',new THREE.BufferAttribute(pos,3));geo.setAttribute('color',new THREE.BufferAttribute(colr,3));scene.add(new THREE.Points(geo,new THREE.PointsMaterial({size:2.2,vertexColors:true,transparent:true,opacity:.8,sizeAttenuation:true})))}
function build3(){el.innerHTML='';g3=ForceGraph3D()(el).backgroundColor('#06090F').graphData(visible()).nodeLabel(()=>null).nodeVal(n=>nodeSize(n)).nodeThreeObject(nodeObj).nodeThreeObjectExtend(false)
 .linkCurvature(.18).linkColor(l=>l.rel==='loads'?'rgba(57,201,182,.45)':l.rel==='owns'||l.rel==='runs'?'rgba(224,180,92,.7)':l.rel==='member'?'rgba(242,127,165,.28)':'rgba(140,160,190,.25)').linkWidth(l=>l.rel==='owns'?1.4:l.rel==='runs'?1:.45).linkOpacity(.6)
 .linkDirectionalParticles(l=>l.rel==='owns'||l.rel==='runs'?3:l.rel==='loads'?2:0).linkDirectionalParticleWidth(1.6).linkDirectionalParticleSpeed(.005).linkDirectionalParticleColor(l=>l.rel==='loads'?'#39C9B6':'#E0B45C')
 .linkLabel(l=>`<span style="font:12px IBM Plex Mono;color:#93A4B3;background:rgba(10,16,26,.9);padding:3px 7px;border-radius:6px">${(l.source.label||l.source)} <b style="color:#E0B45C">${l.rel}</b> ${(l.target.label||l.target)}</span>`)
 .onNodeHover(n=>{el.style.cursor=n?'pointer':null;if(n){const c=g3.graph2ScreenCoords(n.x,n.y,n.z);showTip(n,c.x,c.y)}else showTip(null)}).onNodeClick(n=>focusNode(n)).onBackgroundClick(()=>showFocus(null));
 const scene=g3.scene();scene.add(new THREE.AmbientLight(0x8899aa,.9));const key=new THREE.DirectionalLight(0xffffff,1.1);key.position.set(200,300,250);scene.add(key);const rim=new THREE.PointLight(0x39C9B6,.9,900);rim.position.set(-250,-120,-200);scene.add(rim);addStars(scene);
 g3.d3Force('charge').strength(-95);g3.d3Force('center',null);g3.d3Force('link').distance(l=>l.rel==='member'?18:l.rel==='owns'?75:l.rel==='loads'?42:32);
 const ctl=g3.controls();ctl.autoRotate=rotating;ctl.autoRotateSpeed=.45;ctl.enableDamping=true;
 setTimeout(()=>{g3.zoomToFit(700,70);setTimeout(()=>g3.cameraPosition(undefined,{x:0,y:0,z:0},600),750)},900)}
function build2(){el.innerHTML='';g2=ForceGraph()(el).backgroundColor('#06090F').graphData(visible()).nodeLabel(()=>null).nodeVal(n=>nodeSize(n)).nodeColor(n=>COL[n.type]).linkColor(l=>l.rel==='loads'?'rgba(57,201,182,.45)':l.rel==='owns'?'rgba(224,180,92,.7)':'rgba(140,160,190,.25)').linkWidth(l=>l.rel==='owns'?1.5:.5).linkDirectionalParticles(l=>l.rel==='owns'||l.rel==='loads'?2:0).linkDirectionalParticleWidth(2).linkDirectionalParticleColor(l=>l.rel==='loads'?'#39C9B6':'#E0B45C')
 .nodeCanvasObjectMode(()=>'after').nodeCanvasObject((n,ctx,scale)=>{if(!labels)return;if(n.type==='Agent'&&scale<2.2&&!query)return;const fs=Math.max(10,(n.type==='HQ'?22:n.type==='Department'?16:11))/scale;ctx.font=`${fs}px IBM Plex Sans`;ctx.textAlign='center';ctx.fillStyle=COL[n.type];ctx.fillText(n.label,n.x,n.y+nodeSize(n)/1.2+fs)})
 .onNodeHover(n=>{el.style.cursor=n?'pointer':null;if(n){const c=g2.graph2ScreenCoords(n.x,n.y);showTip(n,c.x,c.y)}else showTip(null)}).onNodeClick(n=>focusNode(n)).onBackgroundClick(()=>showFocus(null));
 g2.d3Force('charge').strength(-120);g2.d3Force('center',null);setTimeout(()=>g2.zoomToFit(600,40),900)}
function focusNode(n){if(!n)return;showFocus(n);if(mode==='3d'&&g3){const d=90,r=Math.hypot(n.x,n.y,n.z)||1;g3.cameraPosition({x:n.x*(1+d/r),y:n.y*(1+d/r),z:n.z*(1+d/r)},n,1200)}else if(g2){g2.centerAt(n.x,n.y,800);g2.zoom(4,800)}}
function redraw(){const d=visible();(mode==='3d'?g3:g2).graphData(d);status()}
function status(){const d=visible();document.getElementById('st').innerHTML=`Showing ${d.nodes.length} of ${G.nodes.length} nodes · hover to inspect · click to focus · drag to move<br><a href="https://github.com/kamelhijawi/elysian-hq">kamelhijawi/elysian-hq</a> · sales ${G.meta.sales_commits} commits · marketing ${G.meta.mkt_commits} commits`}
document.getElementById('b3').onclick=()=>{mode='3d';document.getElementById('b3').classList.add('on');document.getElementById('b2').classList.remove('on');build3();status()};
document.getElementById('b2').onclick=()=>{mode='2d';document.getElementById('b2').classList.add('on');document.getElementById('b3').classList.remove('on');build2();status()};
document.getElementById('rot').onclick=e=>{rotating=!rotating;if(g3)g3.controls().autoRotate=rotating;e.target.textContent=rotating?'Pause orbit':'Resume orbit'};
document.getElementById('fit').onclick=()=>{mode==='3d'?g3.zoomToFit(600,60):g2.zoomToFit(600,40)};
document.getElementById('lab').onclick=e=>{labels=!labels;e.target.classList.toggle('off');mode==='3d'?g3.nodeThreeObject(nodeObj):g2.nodeCanvasObject(g2.nodeCanvasObject())};
document.getElementById('q').oninput=e=>{query=e.target.value.trim().toLowerCase();redraw()};
build3();status();
</script>
"""
(HQ/"private").mkdir(exist_ok=True)
(HQ/"private/index.html").write_text(page.replace("__DATA__",J_PRIVATE).replace("<span>live</span>","<span>private</span>"),encoding="utf-8")
page=page.replace("__DATA__",J)
(HQ/"index.html").write_text(page,encoding="utf-8")
print(json.dumps({"nodes":len(nodes),"links":len(links),"types":counts}))
