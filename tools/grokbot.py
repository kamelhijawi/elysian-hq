#!/usr/bin/env python3
"""Run one department recipe on Grok (xAI). Usage: grokbot.py <brain_dir> <recipe.md> [--model grok-4.6] [--dry]
Loads CLAUDE.md, the recipe, and every file on the recipe's LOAD: line (paths relative to brain_dir, ../ allowed),
asks Grok to produce the recipe's output, appends it to the recipe's target file (or live/runs/), commits.
Key comes from macOS Keychain (hq/tools/xai-key.sh). Web search is enabled for roles that read the market."""
import sys, re, json, pathlib, subprocess, datetime, urllib.request
args=sys.argv[1:]
model="grok-4.6"; dry="--dry" in args
if "--model" in args: model=args[args.index("--model")+1]
pos=[a for a in args if not a.startswith("--") and a!=model]
brain=pathlib.Path(pos[0]).resolve(); recipe=brain/pos[1]
HQ=pathlib.Path(__file__).resolve().parent.parent
key=subprocess.check_output([str(HQ/"tools/xai-key.sh")],text=True).strip()
today=datetime.date.today().isoformat()
def read(p):
    p=(brain/p).resolve()
    return p.read_text(errors="ignore") if p.exists() else f"(missing: {p})"
rtxt=recipe.read_text()
loads=[]
m=re.search(r"^LOAD:\s*(.+)$",rtxt,re.M)
if m:
    for item in re.split(r",\s*",m.group(1)):
        item=item.strip()
        if item.endswith("/*"):
            d=(brain/item[:-2]).resolve()
            loads+= [str(p.relative_to(brain)) if brain in p.parents else str(p) for p in sorted(d.glob("*.md"))] if d.exists() else []
        elif item and not item.startswith("latest"):
            loads.append(item)
ctx="\n\n".join(f"===== {l} =====\n{read(l)}" for l in loads)
# target file per role
TARGET={"creative-director":"live/ideas.md","market-analyst":"live/week.md","reporter":"live/week.md",
        "media-planner":"live/media-plans.md","campaign-planner":None}
role=recipe.stem; target=TARGET.get(role)
system=("You are one role in an AI department for Elysian Real Estate, Dubai. You follow the recipe exactly, "
        "write in the voice rules provided, use only facts in the files or facts you verify with search, "
        "never invent a number, mark unknowns as << fill: ... >>. Output ONLY the content to append to the target file, "
        "in the exact row or block format the recipe and target file use. Today is "+today+".")
user=(f"DEPARTMENT RULES (CLAUDE.md):\n{read('CLAUDE.md')}\n\nRECIPE ({recipe.name}):\n{rtxt}\n\nLOADED FILES:\n{ctx}\n\n"
      f"TARGET FILE (append to this; keep its format): {target or 'live/runs/'+today+'-'+role+'.md'}\n"
      f"Current target content:\n{read(target) if target else '(new file)'}\n\nProduce the output now.")
body={"model":model,"input":[{"role":"system","content":system},{"role":"user","content":user}],"max_output_tokens":4000}
if role in ("market-analyst","creative-director"):
    body["tools"]=[{"type":"web_search"}]
req=urllib.request.Request("https://api.x.ai/v1/responses",data=json.dumps(body).encode(),
    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"})
with urllib.request.urlopen(req,timeout=600) as r: resp=json.load(r)
out="".join(c.get("text","") for o in resp.get("output",[]) if o.get("type")=="message" for c in o.get("content",[])).strip()
# drop any narration before the first real block/row
mm=re.search(r"^(## |\d{4}-\d{2}-\d{2} \|)",out,re.M)
if mm: out=out[mm.start():]
usage=resp.get("usage",{})
stamp=f"\n\n<!-- grokbot {model} {datetime.datetime.now():%Y-%m-%d %H:%M} tokens={usage.get('total_tokens')} -->\n"
if dry: print(out); sys.exit(0)
dest=brain/(target or f"live/runs/{today}-{role}.md"); dest.parent.mkdir(parents=True,exist_ok=True)
with open(dest,"a",encoding="utf-8") as f: f.write(stamp+out+"\n")
subprocess.call(["git","-C",str(brain),"add","-A"]); subprocess.call(["git","-C",str(brain),"commit","-q","-m",f"grokbot: {role} {today} ({model})"])
print(json.dumps({"role":role,"model":resp.get("model"),"tokens":usage.get("total_tokens"),"wrote":str(dest.relative_to(brain))}))
