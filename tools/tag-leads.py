#!/usr/bin/env python3
"""tag-leads.py --merge <dir-with-json-pages> — merges Salesforce pages (Lead / Task / Event query results) into the local store,
tags every lead, and writes the board view. Deterministic, no AI.
  store:  moonshelter/live/leads/store.json   (git-ignored: client names and comments)
  view:   moonshelter/live/leads/latest.json  (git-ignored; the board reads it)
  counts: moonshelter/live/leads/YYYY-MM-DD.md (committed: counts per team and agent, no names)
Tags per lead: NOT_UPDATED (open, no agent activity for 48h+ and no first call, or nothing logged for 7d),
POSITIVE / NEGATIVE (from status, call outcomes and comment wording), MEETING (booked: status Meeting, a Meeting task/event, a confirmed appointment,
next action 'Meeting Proposed' or 'Waiting for site visit'), POTENTIAL (comments talk about a viewing/meeting/visit but nothing is booked)."""
import json, sys, re, pathlib, datetime, zoneinfo, collections
E=pathlib.Path.home()/"elysian"; D=E/"moonshelter/live/leads"; D.mkdir(parents=True,exist_ok=True)
STORE=D/"store.json"; VIEW=D/"latest.json"; DXB=zoneinfo.ZoneInfo("Asia/Dubai"); NOW=datetime.datetime.now(datetime.timezone.utc)
def iso(s):
    if not s: return None
    s=s.replace("Z","+00:00"); s=re.sub(r"([+-]\d{2})(\d{2})$",r"\1:\2",s)
    try: return datetime.datetime.fromisoformat(s)
    except ValueError: return None
def hours_since(s):
    d=iso(s); return round((NOW-d).total_seconds()/3600,1) if d else None
def dxb(s):
    d=iso(s); return d.astimezone(DXB).strftime("%a %d %b %H:%M") if d else ""
# roster
AG={}; LEADS_OF={}
for l in (E/"brain/ref/team.md").read_text().splitlines():
    m=re.match(r"\s+- (.+?) — (.+?) — \d+",l)
    if m: LEADS_OF[m.group(2).strip()]=re.sub(r"\s*\(.*?\)","",m.group(1)).strip()
    if l.startswith("| ") and "---" not in l and not l.startswith("| Agent") and not l.startswith("| Name"):
        c=[x.strip() for x in l.strip().strip("|").split("|")]
        if len(c)>=10 and c[7].startswith("005"): AG[c[7]]={"id":c[7],"name":c[0],"team":c[1],"email":c[8]}
TEAM_ORDER=["Secondary","Team 1","Team 2","Team 3","ELITE"]
POS=re.compile(r"\b(interested|keen|wants?|would like|looking (for|to)|budget|down ?payment|pre-?approv|mortgage approved|cash buyer|ready to|send (me )?(the )?(details|options|brochure)|viewing|site visit|meeting|visit (the )?(site|office|project)|call back|callback|follow ?up|will call (me )?back|sending (him|her) options|shortlist|offer|negotiat|booking|reserve|eoi|token)\b",re.I)
NEG=re.compile(r"\b(not interested|no longer|already (bought|rented|found|closed)|wrong number|wrong no|number not found|no\. not found|invalid number|spam|he'?s an agent|she'?s an agent|is an agent|broker|agency|do not call|don'?t call|stop calling|remove|unsubscribe|rude|hung up|out of budget|too expensive|can'?t afford|no budget|not looking|just browsing|lost)\b",re.I)
MEET=re.compile(r"\b(viewing|site visit|meeting|meet (him|her|the client|on|at|tomorrow|today)|visit (the )?(site|office|project|sales centre)|come to (the )?office|show (him|her) the|appointment|tour)\b",re.I)
BOOKED=re.compile(r"\b(booked|confirmed|scheduled|fixed|set) (a |the )?(viewing|meeting|site visit|appointment)|(viewing|meeting|site visit|appointment) (is )?(booked|confirmed|scheduled|fixed|set|tomorrow|on (mon|tue|wed|thu|fri|sat|sun))",re.I)
def load_pages(d):
    L,T,V={},{},{}
    for p in sorted(list(pathlib.Path(d).glob("*.json"))+list(pathlib.Path(d).glob("*.txt"))):
        try: j=json.loads(p.read_text())
        except Exception: continue
        recs=j.get("records",j if isinstance(j,list) else [])
        for r in recs:
            t=(r.get("attributes") or {}).get("type") or ("Lead" if r.get("Id","").startswith("00Q") else "Task" if r.get("Id","").startswith("00T") else "Event" if r.get("Id","").startswith("00U") else "")
            r=dict(r); r.pop("attributes",None)
            {"Lead":L,"Task":T,"Event":V}.get(t,{})[r["Id"]]=r
    return L,T,V
def tag(lead,tasks,events):
    tags=set(); why=[]
    st=lead.get("Status") or ""; nxt=lead.get("Next_Action__c") or ""
    comments=" ".join(x for x in (lead.get("Activity_Comments__c"),lead.get("Comments_Log__c"),lead.get("Sales_Manager_Feedback__c"),lead.get("Description")) if x)
    tdesc=" ".join((t.get("Description") or "")+" "+(t.get("Subject") or "") for t in tasks)
    text=comments+" "+tdesc
    outcomes=[t.get("Call_Outcome__c") or "" for t in tasks]
    last_act=max([x for x in (lead.get("Last_Activity_Action_Date__c"),lead.get("Last_Call_Date__c"),lead.get("First_Call_Date_Time__c"))+tuple(t.get("CreatedDate") for t in tasks) if x],default=None)
    h_act=hours_since(last_act) if last_act else None; h_cre=hours_since(lead.get("CreatedDate")) or 0
    # meetings
    booked=[e for e in events if (e.get("Type") or "") in ("Meeting","Viewing","Appointment","Property Inspection") and (e.get("Appointment_Status__c") or "")!="Cancelled"]
    mt=[t for t in tasks if (t.get("Type") or "")=="Meeting" or (t.get("Appointment_Status__c") or "") in ("Confirmed","Unconfirmed")]
    if st=="Meeting" or booked or mt or nxt in ("Meeting Proposed","Waiting for site visit") or BOOKED.search(text):
        tags.add("MEETING"); why.append("status Meeting" if st=="Meeting" else "event booked" if booked else "meeting task" if mt else f"next action {nxt}" if nxt else "booked in comments")
    elif MEET.search(text): tags.add("POTENTIAL"); why.append("viewing/meeting mentioned: "+MEET.search(text).group(0))
    # sentiment
    if st in ("Unqualified","Closed") or "Lost" in outcomes or NEG.search(text):
        tags.add("NEGATIVE"); why.append("status "+st if st in ("Unqualified","Closed") else "outcome Lost" if "Lost" in outcomes else "comment: "+NEG.search(text).group(0))
    elif st in ("Qualified","Working","Meeting") or any(o.startswith("In Progress - Contacted") for o in outcomes) or POS.search(text):
        tags.add("POSITIVE"); why.append("status "+st if st in ("Qualified","Working","Meeting") else "outcome contacted" if any(o.startswith("In Progress - Contacted") for o in outcomes) else "comment: "+POS.search(text).group(0))
    # not updated: open, and either no activity ever after 48h, or no activity for 7 days
    if st in ("New","Working","Not Reachable") and ((h_act is None and h_cre>=48) or (h_act is not None and h_act>=168)):
        tags.add("NOT_UPDATED"); why.append(f"no activity {'ever' if h_act is None else 'for %d days'%int(h_act//24)}")
    return sorted(tags),why,last_act
def main():
    if len(sys.argv)<3 or sys.argv[1]!="--merge": print(__doc__); sys.exit(2)
    store=json.loads(STORE.read_text()) if STORE.exists() else {"leads":{},"tasks":{},"events":{},"pulls":[]}
    L,T,V=load_pages(sys.argv[2])
    store["leads"].update(L); store["tasks"].update(T); store["events"].update(V)
    stamp=NOW.astimezone(DXB).strftime("%Y-%m-%d %H:%M"); store["pulls"]=(store.get("pulls",[])+[{"at":stamp,"leads":len(L),"tasks":len(T),"events":len(V)}])[-200:]
    store["last_pull_utc"]=NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    # drop converted / very old
    cutoff=NOW-datetime.timedelta(days=45)
    store["leads"]={k:v for k,v in store["leads"].items() if not v.get("IsConverted") and (iso(v.get("CreatedDate")) or NOW)>=cutoff}
    STORE.write_text(json.dumps(store,ensure_ascii=False))
    by_lead_t=collections.defaultdict(list); by_lead_e=collections.defaultdict(list)
    for t in store["tasks"].values(): by_lead_t[t.get("WhoId")].append(t)
    for e in store["events"].values(): by_lead_e[e.get("WhoId")].append(e)
    agents={aid:{**a,"leads":[]} for aid,a in AG.items()}; outside=collections.Counter()
    for lid,l in store["leads"].items():
        o=l.get("OwnerId")
        if o not in agents: outside[(l.get("Owner") or {}).get("Name") or o]+=1; continue
        ts=sorted(by_lead_t.get(lid,[]),key=lambda t:t.get("CreatedDate") or "",reverse=True); es=by_lead_e.get(lid,[])
        tags,why,last_act=tag(l,ts,es)
        nm=(l.get("Name") or "").strip(); w=nm.split()
        if len(w)%2==0 and w[:len(w)//2]==w[len(w)//2:]: nm=" ".join(w[:len(w)//2])
        seg={"Residential Tenant":"rental","Residential Buyer":"resale","Elysian Off Plan":"off-plan"}.get((l.get("RecordType") or {}).get("Name") or "",((l.get("RecordType") or {}).get("Name") or "").lower())
        last_comment=""; last_comment_at=""
        if ts and (ts[0].get("Description") or "").strip(): last_comment=ts[0]["Description"].strip(); last_comment_at=ts[0].get("CreatedDate")
        elif l.get("Activity_Comments__c"): last_comment=l["Activity_Comments__c"].strip(); last_comment_at=l.get("Last_Activity_Action_Date__c") or l.get("LastModifiedDate")
        nxt_e=sorted([e for e in es if iso(e.get("StartDateTime")) and iso(e["StartDateTime"])>=NOW-datetime.timedelta(days=1)],key=lambda e:e["StartDateTime"])
        agents[o]["leads"].append({"id":lid,"name":nm,"source":l.get("LeadSource") or "blank","segment":seg,"what":l.get("Project__c") or l.get("Listing_Reference_Number__c") or "",
            "status":l.get("Status"),"rating":l.get("Rating"),"created":dxb(l.get("CreatedDate")),"created_h":hours_since(l.get("CreatedDate")),
            "last_activity":dxb(last_act) if last_act else "","last_activity_h":hours_since(last_act) if last_act else None,
            "last_outcome":(ts[0].get("Call_Outcome__c") if ts else "") or "","last_comment":last_comment[:400],"last_comment_at":dxb(last_comment_at),
            "next_action":l.get("Next_Action__c") or "","next_action_date":l.get("Next_Action_date__c") or "",
            "meeting":(f"{nxt_e[0].get('Type')} {dxb(nxt_e[0].get('StartDateTime'))}" if nxt_e else ""),"tags":tags,"why":why[:3],"tasks_7d":len(ts)})
    teams=collections.OrderedDict((t,{"team":t,"lead":LEADS_OF.get(t,""),"agents":[],"counts":collections.Counter()}) for t in TEAM_ORDER)
    for a in sorted(agents.values(),key=lambda a:(TEAM_ORDER.index(a["team"]) if a["team"] in TEAM_ORDER else 9,a["name"])):
        c=collections.Counter(); c["leads"]=len(a["leads"])
        for l in a["leads"]:
            for t in l["tags"]: c[t]+=1
        a["counts"]=dict(c); a["leads"].sort(key=lambda l:(-(l["last_activity_h"] or 1e9) if "NOT_UPDATED" in l["tags"] else 0, l["created"]))
        a["leads"].sort(key=lambda l:(0 if "MEETING" in l["tags"] else 1 if "POTENTIAL" in l["tags"] else 2 if "NOT_UPDATED" in l["tags"] else 3, -(l["created_h"] or 0)))
        t=teams.setdefault(a["team"],{"team":a["team"],"lead":"","agents":[],"counts":collections.Counter()}); t["agents"].append(a); t["counts"].update(c)
    total=collections.Counter()
    for t in teams.values(): t["counts"]=dict(t["counts"]); total.update(t["counts"])
    view={"generated":stamp,"window_days":30,"totals":dict(total),"outside_roster":dict(outside.most_common(10)),"teams":list(teams.values()),"tag_help":{
        "NOT_UPDATED":"open lead with no agent activity after 48h, or none for 7 days","POSITIVE":"status Working/Qualified/Meeting, contacted outcome, or positive wording in comments",
        "NEGATIVE":"Unqualified/Closed, Lost outcome, or negative wording (spam, agent, not interested, wrong number)","MEETING":"a meeting or viewing is booked (status, event, task, next action or comments)","POTENTIAL":"comments mention a viewing or meeting but nothing is booked yet"}}
    VIEW.write_text(json.dumps(view,ensure_ascii=False))
    md=[f"# Leads pulse — {stamp}",f"Window: leads created in the last {view['window_days']} days, rostered agents. Pull: {len(L)} leads, {len(T)} tasks, {len(V)} events merged. Counts only; names stay in the git-ignored store.","",
        "| Team | Agent | Leads | Not updated | Positive | Negative | Meeting | Potential |","|---|---|---|---|---|---|---|---|"]
    for t in view["teams"]:
        c=t["counts"]; md.append(f"| {t['team']} | ALL | {c.get('leads',0)} | {c.get('NOT_UPDATED',0)} | {c.get('POSITIVE',0)} | {c.get('NEGATIVE',0)} | {c.get('MEETING',0)} | {c.get('POTENTIAL',0)} |")
        for a in t["agents"]:
            c=a["counts"]; md.append(f"| {t['team']} | {a['name']} | {c.get('leads',0)} | {c.get('NOT_UPDATED',0)} | {c.get('POSITIVE',0)} | {c.get('NEGATIVE',0)} | {c.get('MEETING',0)} | {c.get('POTENTIAL',0)} |")
    (D/f"{NOW.astimezone(DXB):%Y-%m-%d}.md").write_text("\n".join(md)+"\n")
    print(json.dumps({"generated":stamp,"merged":{"leads":len(L),"tasks":len(T),"events":len(V)},"store":{"leads":len(store["leads"]),"tasks":len(store["tasks"]),"events":len(store["events"])},"totals":dict(total),"outside_roster":dict(outside.most_common(5))},indent=1))
if __name__=="__main__": main()
