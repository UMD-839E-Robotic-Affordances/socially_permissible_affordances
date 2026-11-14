#!/usr/bin/env python3
"""Interactive reviewer for scenarios.py.

Run:  python3 review.py [--out reviewed.json] [--port N]

Opens a local web page that steps through each Scenario. You can edit every
field, add notes, and ask Claude (via the `claude` CLI) to revise the scenario;
its proposal is loaded into the form for you to accept or tweak before saving.
Results are written to a JSON file (default: reviewed.json) after every save,
and the session resumes from the first unreviewed scenario on restart.
"""
import argparse
import difflib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True  # reloading an edited scenarios.py must never hit a stale .pyc
import scenarios

FIELDS = ["context", "goal", "action", "object", "judgment", "tags", "summary"]
JUDGMENTS = ["accept", "reject", "uncertain"]

BASE = os.path.dirname(os.path.abspath(scenarios.__file__))
CATS_PATH = os.path.join(BASE, "categories.json")   # taxonomy: groups, labels, definitions

lock = threading.Lock()
OUT_PATH = "reviewed.json"


def original(s):
    d = s._asdict()
    d["tags"] = list(d["tags"])
    return d


def load_saved():
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH) as f:
            return json.load(f)
    return {}


def write_json(path, data):
    # atomic write so a crash never corrupts the file
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def write_saved(data):
    write_json(OUT_PATH, data)


_scen_mtime = None


def scs():
    """Current SCENARIOS, reloading scenarios.py if it changed on disk."""
    global _scen_mtime
    m = os.stat(scenarios.__file__).st_mtime_ns
    if m != _scen_mtime:
        try:
            importlib.invalidate_caches()
            importlib.reload(scenarios)
        except Exception:
            pass  # file may be mid-edit; keep the last good list
        _scen_mtime = m
    return scenarios.SCENARIOS


def load_cats():
    if os.path.exists(CATS_PATH):
        with open(CATS_PATH) as f:
            return json.load(f)
    return {"groups": [], "categories": {}}


def taxonomy():
    c = load_cats()
    groups = {g: [] for g in c["groups"]}
    labels, defs, subs = {}, {}, {}
    for tag, m in c["categories"].items():
        if m.get("subgroup"):
            subs[tag] = m["subgroup"]
        if m.get("group"):
            groups.setdefault(m["group"], []).append(tag)
        if m.get("label"):
            labels[tag] = m["label"]
        defs[tag] = m.get("definition", "")
    subdefs = {n: v.get("definition", "") for n, v in c.get("subgroups", {}).items()}
    return {"groups": groups, "labels": labels, "defs": defs, "subs": subs, "subdefs": subdefs}


def categories_view():
    c = load_cats()
    use = {}
    for it in state():
        for t in it["current"]["tags"]:
            use.setdefault(t, []).append(it["id"])
    rows = [{"tag": t, "label": m.get("label") or "", "group": m.get("group") or "",
             "definition": m.get("definition", ""), "subgroup": m.get("subgroup") or "",
             "ids": use.get(t, []), "defined": True}
            for t, m in c["categories"].items()]
    rows += [{"tag": t, "label": "", "group": "", "definition": "", "subgroup": "", "ids": ids, "defined": False}
             for t, ids in use.items() if t not in c["categories"]]
    subgroups = [{"name": n, "group": v.get("group", ""), "definition": v.get("definition", "")}
                 for n, v in c.get("subgroups", {}).items()]
    return {"groups": c["groups"], "subgroups": subgroups, "rows": rows}


def save_category(body):
    tag = body["tag"].strip()
    group = (body.get("group") or "").strip()
    with lock:
        c = load_cats()
        if group and group not in c["groups"]:
            raise ValueError(f"unknown group {group!r}")
        sub = (body.get("subgroup") or "").strip()
        if sub and c.get("subgroups", {}).get(sub, {}).get("group") != group:
            raise ValueError(f"subgroup {sub!r} does not belong to group {group!r}")
        entry = {"label": (body.get("label") or "").strip() or None,
                 "group": group or None,
                 "definition": body.get("definition", "").strip()}
        if sub:
            entry["subgroup"] = sub
        if "reviewer_notes" in c["categories"].get(tag, {}):  # not editable here; keep it
            entry["reviewer_notes"] = c["categories"][tag]["reviewer_notes"]
        c["categories"][tag] = entry
        write_json(CATS_PATH, c)
    return {"ok": True}


def state():
    saved = load_saved()
    items = []
    for s in scs():
        o = original(s)
        rec = saved.get(s.id)
        items.append({
            "id": s.id,
            "original": o,
            "current": {k: rec.get(k, o[k]) for k in FIELDS} if rec else o,
            "notes": rec["notes"] if rec else "",
            "reviewed": bool(rec),
            "changed": bool(rec) and any(rec.get(k, o[k]) != o[k] for k in FIELDS),
        })
    return items


def clean(fields):
    tags = fields.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    summary = (fields.get("summary") or "").strip() or None
    return {
        "context": fields.get("context", "").strip(),
        "goal": fields.get("goal", "").strip(),
        "action": fields.get("action", "").strip(),
        "object": (fields.get("object") or "").strip() or None,
        "judgment": fields.get("judgment", "uncertain"),
        "tags": [t for t in tags if t],
        "summary": summary,
    }


def save(body):
    sid = body["id"]
    o = next((original(s) for s in scs() if s.id == sid), None)
    if o is None:
        raise ValueError(f"unknown id {sid}")
    f = clean(body["fields"])
    if f["judgment"] not in JUDGMENTS:
        raise ValueError("bad judgment")
    rec = {"id": sid, **f, "notes": body.get("notes", "").strip(),
           "changed": any(f[k] != o[k] for k in FIELDS),
           "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with lock:
        saved = load_saved()
        saved[sid] = rec
        # keep file in scenario order
        order = {s.id: i for i, s in enumerate(scs())}
        write_saved(dict(sorted(saved.items(), key=lambda kv: order.get(kv[0], 1e9))))
    return rec


def ask_claude(body):
    cur = clean(body["fields"])
    prompt = (
        "You are helping revise one entry in a dataset of robot-affordance "
        "scenarios (context, goal, action, object (the thing, resource or space the action uses or affects, or null), a judgment of accept/reject/uncertain, "
        "tags, and an optional summary).\n\n"
        f"Current entry:\n{json.dumps(cur, indent=2)}\n\n"
        f"Reviewer notes so far: {body.get('notes') or '(none)'}\n\n"
        f"Reviewer request: {body['request']}\n\n"
        "Apply the request, changing only what it implies. Reply with ONLY a JSON "
        "object with exactly these keys: context, goal, action, object (string or null), judgment "
        "(accept|reject|uncertain), tags (array of strings), summary (string or "
        "null), and comment (one or two sentences on what you changed and why). "
        "No code fences, no other text."
    )
    r = subprocess.run(["claude", "-p", prompt, "--tools", ""],
                       capture_output=True, text=True, timeout=180,
                       cwd=tempfile.gettempdir())
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "claude exited with an error")
    m = re.search(r"\{.*\}", r.stdout, re.S)
    if not m:
        raise RuntimeError("no JSON in reply: " + r.stdout[:300])
    out = json.loads(m.group(0))
    comment = out.pop("comment", "")
    new = clean(out)
    if new["judgment"] not in JUDGMENTS:
        raise RuntimeError(f"bad judgment from claude: {new['judgment']}")
    return {"fields": new, "comment": comment}


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _core():
    return [(x.id, x.context, x.goal, x.action, x.object, x.judgment, x.summary) for x in scs()]


def _validate():
    """Return an error string if the edited files are unusable, else None."""
    try:
        c = json.loads(_read(CATS_PATH))
        assert isinstance(c["groups"], list) and isinstance(c["categories"], dict), "bad categories.json shape"
        for t, m in c["categories"].items():
            assert not m.get("group") or m["group"] in c["groups"], f"{t}: unknown group {m['group']!r}"
            sg = m.get("subgroup")
            assert not sg or c.get("subgroups", {}).get(sg, {}).get("group") == m.get("group"), \
                f"{t}: subgroup {sg!r} missing or in a different group"
        if os.path.exists(OUT_PATH):
            json.loads(_read(OUT_PATH))
        global _scen_mtime
        _scen_mtime = None
        ids = [x.id for x in scs()]
        assert len(ids) == len(set(ids)), "duplicate scenario ids"
        for x in scs():
            assert isinstance(x.tags, tuple) and all(isinstance(t, str) for t in x.tags), f"{x.id}: bad tags"
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def ask_categories(body):
    req = body["request"].strip()
    this_file = os.path.abspath(__file__)
    files = {"categories.json": CATS_PATH, "scenarios.py": scenarios.__file__, "review.py": this_file}
    reviewed_name = os.path.basename(OUT_PATH)
    if os.path.exists(OUT_PATH):
        files[reviewed_name] = OUT_PATH
    with lock:
        scs()
        before = {n: _read(p) for n, p in files.items()}
        core_before = _core()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bdir = os.path.join(BASE, ".backups", stamp)
        os.makedirs(bdir, exist_ok=True)
        for n, txt in before.items():
            with open(os.path.join(bdir, n), "w", encoding="utf-8") as f:
                f.write(txt)
        prompt = (
            "You maintain the category taxonomy for a dataset of robot-affordance scenarios.\n\n"
            f"Files (all editable except review.py):\n"
            f"- {CATS_PATH}: JSON {{groups: [...], categories: {{tag: {{label, group, definition}}}}}}. "
            "This is the taxonomy shown in the UI. Hierarchy: groups, then optional subgroups "
            "(top-level \"subgroups\": {name: {group, definition}}; a category may carry a \"subgroup\" naming one "
            "whose group matches its own). Subgroups are headings, not tags.\n"
            f"- {scenarios.__file__}: the dataset. Each Scenario has tags=(...) listing category tags.\n"
            + (f"- {OUT_PATH}: saved human reviews; each entry has a \"tags\" list.\n"
               if os.path.exists(OUT_PATH) else "- (no saved reviews file exists yet)\n")
            + f"\nReviewer request: {req}\n\n"
            "Rules:\n"
            "- Make the minimum edits that satisfy the request.\n"
            "- Renaming, merging, splitting or removing a tag must be applied consistently: "
            "categories.json, every tags tuple in scenarios.py, and every \"tags\" list in the reviews file. "
            "Dedupe tags within a scenario and keep the trailing comma on one-element tuples.\n"
            "- When merging, write a definition for the surviving category that covers both. "
            "Every tag used in scenarios.py should have an entry in categories.json with a group from \"groups\".\n"
            "- Do not change any other Scenario field (id, context, goal, action, object, judgment, summary), "
            "scenario order, or review.py. Keep valid Python and JSON.\n"
            "- When finished, reply with 1-3 plain sentences saying what you changed."
        )
        cmd = ["claude", "-p", prompt, "--permission-mode", "acceptEdits", "--tools", "Read,Edit,Write,Grep"]
        out_dir = os.path.dirname(os.path.abspath(OUT_PATH))
        if out_dir != BASE:
            cmd += ["--add-dir", out_dir]

        def restore():
            global _scen_mtime
            for n, p in files.items():
                with open(p, "w", encoding="utf-8") as f:
                    f.write(before[n])
            _scen_mtime = None
            scs()

        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=BASE)
        except Exception:
            restore()
            raise
        err = None
        if r.returncode != 0:
            err = r.stderr.strip() or "claude exited with an error"
        elif _read(this_file) != before["review.py"]:
            err = "Claude modified review.py, which is not allowed"
        else:
            err = _validate()
            if not err and _core() != core_before:
                err = "scenario text fields (not tags) were changed"
        if err:
            restore()
            raise RuntimeError(f"{err}. Nothing was changed (files restored from backup).")
        changed, diff = [], []
        for n, p in files.items():
            after = _read(p)
            if after != before[n]:
                changed.append(n)
                diff += difflib.unified_diff(before[n].splitlines(), after.splitlines(),
                                             f"a/{n}", f"b/{n}", lineterm="", n=0)
        text = "\n".join(diff)
        if len(text) > 30000:
            text = text[:30000] + "\n… (diff truncated)"
        return {"comment": r.stdout.strip(), "changed": changed, "diff": text,
                "backup": os.path.relpath(bdir, BASE)}


PAGE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Scenario review</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#fafaf8;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--bd:#d9d9d2;--acc:#2a5bd7;--ok:#1d7a3c;--bad:#b3261e;--unc:#9a6a00;--chg:#fff6d6}
@media(prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecece8;--mut:#9a9a93;--card:#1f1f1d;--bd:#3a3a36;--acc:#7ea2ff;--ok:#5fcf85;--bad:#ff8a80;--unc:#e6b84d;--chg:#3a3217}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
header{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px}
h1{font-size:18px;margin:0}.mut{color:var(--mut);font-size:13px}
.bar{height:6px;background:var(--bd);border-radius:3px;overflow:hidden;margin:6px 0 14px}.bar i{display:block;height:100%;background:var(--acc)}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px}
label{display:block;font-weight:600;font-size:13px;margin:12px 0 4px}
textarea,input,select{width:100%;font:inherit;color:inherit;background:var(--bg);border:1px solid var(--bd);border-radius:6px;padding:8px}
textarea{resize:vertical;min-height:2.6em}
.changed{background:var(--chg)}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px;align-items:center}
button{font:inherit;padding:8px 14px;border-radius:6px;border:1px solid var(--bd);background:var(--card);color:var(--fg);cursor:pointer}
button.p{background:var(--acc);color:#fff;border-color:var(--acc)}button:disabled{opacity:.5;cursor:wait}
.sp{flex:1}.pill{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--bd)}
.accept{color:var(--ok)}.reject{color:var(--bad)}.uncertain{color:var(--unc)}
.ask{margin-top:18px;border-top:1px dashed var(--bd);padding-top:6px}
.reply{margin-top:8px;font-size:13px;color:var(--mut);white-space:pre-wrap}
select.jump{width:auto}
.tabs{display:flex;gap:4px}.tabs button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
.cat{margin:8px 0;border-left:4px solid var(--gc,var(--bd))}.cat select{width:auto}
.cat input.lb{max-width:260px}.badge{font-size:11px;padding:1px 6px;border-radius:99px;background:var(--chg)}
details pre{max-height:320px;overflow:auto;font-size:12px;background:var(--bg);padding:8px;border-radius:6px;white-space:pre}
.ids a{cursor:pointer;color:var(--acc);margin-right:8px;font-size:13px}
.sh{font-size:12px;font-weight:600;color:var(--mut);margin:10px 0 2px 6px}.sh span{font-weight:400}
.tg.sub{margin-left:12px;width:calc(100% - 12px)}
.tagdefs{margin-top:6px;font-size:13px;color:var(--mut)}.tagdefs div{margin:2px 0}.tagdefs b{color:var(--fg)}
.wrap{display:flex;gap:16px;align-items:flex-start}.wrap>.card:first-child{flex:1;min-width:0}
aside{width:240px;position:sticky;top:16px;max-height:calc(100vh - 32px);overflow:auto;padding:12px}
aside h2{font-size:13px;margin:0 0 8px}
.tg{display:flex;justify-content:space-between;width:100%;text-align:left;padding:4px 8px;margin:2px 0;font-size:13px}
.gh{display:flex;justify-content:space-between;font-size:12px;text-transform:uppercase;letter-spacing:.05em;margin:12px 0 4px;padding-bottom:3px;border-bottom:2px solid var(--gc,var(--bd))}
.gh:first-child{margin-top:0}.gh span{opacity:.7}
.g-physical{--gc:#d9822b}.g-coordination{--gc:#2a9d8f}.g-social{--gc:#8e5bd7}.g-other{--gc:#888}
.tg{border-left:4px solid var(--gc,var(--bd))}
.tg.on{background:var(--acc);color:#fff;border-color:var(--acc)}.tg span{opacity:.7}
@media(max-width:800px){.wrap{flex-direction:column}aside{width:100%;position:static;max-height:none}}
</style></head><body><main>
<header><h1>Scenario review</h1>
<nav class="tabs"><button id="t-scen" class="on">Scenarios</button><button id="t-cat">Categories</button></nav></header>
<section id="v-scen">
<div class="row" style="margin:0 0 6px"><span class="mut" id="prog"></span><span class="sp"></span>
<select class="jump" id="jump"></select></div>
<div class="bar"><i id="barfill"></i></div>
<div class="wrap"><div class="card">
 <div class="row" style="margin:0"><b id="sid"></b><span class="pill" id="status"></span><span class="sp"></span>
  <button id="revert" title="Reset form to the original scenarios.py values">Revert to original</button></div>
 <label>Context</label><textarea id="context" rows="3"></textarea>
 <label>Goal</label><input id="goal">
 <label>Action</label><input id="action">
 <label>Object <span class="mut">(the thing, resource or space the action uses or affects)</span></label><input id="object">
 <label>Judgment</label><select id="judgment"><option>accept</option><option>reject</option><option>uncertain</option></select>
 <label>Tags (comma-separated)</label><input id="tags"><div class="tagdefs" id="tagdefs"></div>
 <label>Summary (optional)</label><textarea id="summary" rows="2"></textarea>
 <label>Notes</label><textarea id="notes" rows="3" placeholder="Your review notes…"></textarea>
 <div class="ask"><label>Ask Claude to fix something</label>
  <textarea id="req" rows="2" placeholder="e.g. Make the context less ambiguous about who owns the car"></textarea>
  <div class="row"><button id="askbtn">Ask Claude</button><span class="mut">Result is loaded into the form above (highlighted); nothing is saved until you save.</span></div>
  <div class="reply" id="reply"></div></div>
 <div class="row">
  <button id="prev">← Prev</button><button id="next">Next →</button><span class="sp"></span>
  <span class="mut" id="msg"></span>
  <button class="p" id="savenext">Save &amp; next (Ctrl+Enter)</button></div>
</div><aside class="card"><h2>Categories (click a tag to add/remove; hover for definition)</h2><div id="taglist"></div></aside></div>
</section>
<section id="v-cat" hidden>
 <div class="card">
  <label style="margin-top:0">Ask Claude to change the categories</label>
  <textarea id="creq" rows="2" placeholder="e.g. Merge hygiene into contamination · Remove 'risk' and retag its scenarios · Split consent into consent and permission · Add a category for ..."></textarea>
  <div class="row"><button class="p" id="casks">Ask Claude</button>
   <span class="mut">Claude edits categories.json, scenarios.py and your saved reviews directly. A backup goes to .backups/ first, and everything is restored if the result is invalid.</span></div>
  <div class="reply" id="creply"></div>
  <details id="cdiff" hidden><summary>Show changes</summary><pre id="cdifftxt"></pre></details>
 </div>
 <div class="row"><input id="cfilter" placeholder="Filter categories…" style="max-width:260px"><span class="mut" id="ccount"></span>
  <span class="mut">Definition, label and group save automatically when you leave the field.</span></div>
 <div id="clist"></div>
</section></main>
<script>
const F=["context","goal","action","object","judgment","tags","summary"];
let items=[],groups={},labels={},defs={},subs={},subdefs={},cats=null,i=0,orig=null,dirty=false;
const $=id=>document.getElementById(id);
async function api(p,b){const r=await fetch(p,b?{method:"POST",body:JSON.stringify(b)}:{});const j=await r.json();if(!r.ok)throw new Error(j.error||r.status);return j}
function form(){return{context:$("context").value,goal:$("goal").value,action:$("action").value,object:$("object").value,judgment:$("judgment").value,tags:$("tags").value,summary:$("summary").value}}
function fill(f){$("context").value=f.context;$("goal").value=f.goal;$("action").value=f.action;$("object").value=f.object||"";$("judgment").value=f.judgment;$("tags").value=f.tags.join(", ");$("summary").value=f.summary||"";mark()}
function curTags(){return $("tags").value.split(",").map(t=>t.trim()).filter(Boolean)}
function renderTags(){renderDefs();const c={};items.forEach(it=>it.current.tags.forEach(t=>c[t]=(c[t]||0)+1));
 const on=new Set(curTags());on.forEach(t=>c[t]=c[t]||0);
 const box=$("taglist");box.innerHTML="";const placed=new Set();
 const toggle=t=>{const cur=curTags();$("tags").value=(on.has(t)?cur.filter(x=>x!==t):[...cur,t]).join(", ");mark()};
 const section=(name,tags,cls)=>{tags=tags.filter(t=>t in c);if(!tags.length)return;
  tags.sort((x,y)=>c[y]-c[x]||x.localeCompare(y));
  const h=document.createElement("div");h.className="gh "+cls;h.innerHTML="<b></b><span>"+tags.reduce((n,t)=>n+c[t],0)+"</span>";h.firstChild.textContent=name;box.appendChild(h);
  const add=(t,sub)=>{const b=document.createElement("button");b.className="tg "+cls+(sub?" sub":"")+(on.has(t)?" on":"");b.innerHTML="<b></b><span>"+c[t]+"</span>";b.firstChild.textContent=labels[t]||t;b.title=t+(defs[t]?": "+defs[t]:"");b.onclick=()=>toggle(t);box.appendChild(b)};
  tags.filter(t=>!subs[t]).forEach(t=>add(t,false));
  [...new Set(tags.map(t=>subs[t]).filter(Boolean))].forEach(sg=>{const h2=mk("div","sh",sg);h2.title=subdefs[sg]||"";box.appendChild(h2);tags.filter(t=>subs[t]===sg).forEach(t=>add(t,true))})};
 Object.entries(groups).forEach(([g,ts])=>{ts.forEach(t=>placed.add(t));section(g,[...ts],"g-"+g.toLowerCase())});
 section("Other",Object.keys(c).filter(t=>!placed.has(t)),"g-other")}
function renderDefs(){const box=$("tagdefs");box.innerHTML="";
 curTags().forEach(t=>{const d=document.createElement("div");const b=document.createElement("b");b.textContent=labels[t]||t;
  d.appendChild(b);d.appendChild(document.createTextNode(" — "+(defs[t]||"(no definition yet)")));box.appendChild(d)})}
function mark(){renderTags();const o=orig;for(const k of F){const v=form()[k];const ov=k=="tags"?o.tags.join(", "):(o[k]||"");$(k).classList.toggle("changed",v.trim()!==ov.trim())}
 const j=$("judgment");j.className=j.value}
function show(n){i=Math.max(0,Math.min(items.length-1,n));const it=items[i];orig=it.original;
 $("sid").textContent=it.id+"  ("+(i+1)+"/"+items.length+")";
 $("status").textContent=it.reviewed?(it.changed?"reviewed · edited":"reviewed"):"not reviewed";
 fill(it.current);$("notes").value=it.notes;$("req").value="";$("reply").textContent="";$("msg").textContent="";
 $("jump").value=i;prog()}
function prog(){const d=items.filter(x=>x.reviewed).length;$("prog").textContent=d+" of "+items.length+" reviewed";$("barfill").style.width=(100*d/items.length)+"%";
 [...$("jump").options].forEach((o,k)=>o.textContent=items[k].id+(items[k].reviewed?" ✓":"")+" — "+items[k].original.action.slice(0,40))}
async function doSave(){const it=items[i];const r=await api("/api/save",{id:it.id,fields:form(),notes:$("notes").value});
 it.current={context:r.context,goal:r.goal,action:r.action,object:r.object,judgment:r.judgment,tags:r.tags,summary:r.summary};it.notes=r.notes;it.reviewed=true;it.changed=r.changed;renderTags()}
$("savenext").onclick=async()=>{try{await doSave();show(i+1)}catch(e){$("msg").textContent="Save failed: "+e.message}};
$("prev").onclick=()=>show(i-1);$("next").onclick=()=>show(i+1);
$("revert").onclick=()=>fill(orig);
$("jump").onchange=e=>show(+e.target.value);
F.forEach(k=>$(k).addEventListener("input",mark));
$("askbtn").onclick=async()=>{const q=$("req").value.trim();if(!q)return;const b=$("askbtn");b.disabled=true;b.textContent="Asking…";
 try{const r=await api("/api/ask",{fields:form(),notes:$("notes").value,request:q});fill(r.fields);$("reply").textContent="Claude: "+(r.comment||"(updated)")}
 catch(e){$("reply").textContent="Error: "+e.message}b.disabled=false;b.textContent="Ask Claude"};
document.addEventListener("keydown",e=>{if(e.ctrlKey&&e.key=="Enter")$("savenext").click()});
(async()=>{const st=await api("/api/state");items=st.items;groups=st.groups;labels=st.labels;defs=st.defs;subs=st.subs;subdefs=st.subdefs;
 items.forEach((it,k)=>{const o=document.createElement("option");o.value=k;$("jump").appendChild(o)});
 const first=items.findIndex(x=>!x.reviewed);show(first<0?0:first)})();

function formDirty(){const c=items[i].current,f=form();
 return f.context!==c.context||f.goal!==c.goal||f.action!==c.action||(f.object||"")!==(c.object||"")||f.judgment!==c.judgment||
  f.tags.split(",").map(x=>x.trim()).filter(Boolean).join(",")!==c.tags.join(",")||(f.summary||"")!==(c.summary||"")||$("notes").value!==items[i].notes}
async function refreshTax(){const st=await api("/api/state");groups=st.groups;labels=st.labels;defs=st.defs;subs=st.subs;subdefs=st.subdefs;renderTags()}
async function reloadAll(dirty){const st=await api("/api/state");items=st.items;groups=st.groups;labels=st.labels;defs=st.defs;subs=st.subs;subdefs=st.subdefs;
 if(i>=items.length)i=items.length-1;
 if(dirty){orig=items[i].original;mark();prog();$("msg").textContent="Categories changed; your unsaved edits here were kept."}else show(i)}
function tab(n){$("v-scen").hidden=n!=="scen";$("v-cat").hidden=n!=="cat";
 $("t-scen").classList.toggle("on",n==="scen");$("t-cat").classList.toggle("on",n==="cat");if(n==="cat")loadCats()}
$("t-scen").onclick=()=>tab("scen");$("t-cat").onclick=()=>tab("cat");
async function loadCats(){cats=await api("/api/categories");renderCats()}
function mk(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e}
function catCard(r,cls){
 const d=mk("div","card cat "+cls),top=mk("div","row");top.style.margin="0";
 top.appendChild(mk("b",null,r.tag));top.appendChild(mk("span","pill",r.ids.length+" scenario"+(r.ids.length==1?"":"s")));
 if(!r.defined)top.appendChild(mk("span","badge","not defined yet"));else if(!r.ids.length)top.appendChild(mk("span","badge","unused"));
 top.appendChild(mk("span","sp"));const st=mk("span","mut");top.appendChild(st);
 const gs=mk("select");[""].concat(cats.groups).forEach(g=>{const o=mk("option",null,g||"(no group)");o.value=g;gs.appendChild(o)});gs.value=r.group;top.appendChild(gs);
 const ss=mk("select");const fillSubs=()=>{ss.innerHTML="";const o0=mk("option",null,"(no subgroup)");o0.value="";ss.appendChild(o0);
  cats.subgroups.filter(x=>x.group===gs.value).forEach(x=>{const o=mk("option",null,x.name);o.value=x.name;ss.appendChild(o)});ss.value=r.subgroup||"";ss.style.display=ss.options.length>1?"":"none"};
 fillSubs();top.appendChild(ss);
 d.appendChild(top);
 d.appendChild(mk("label",null,"Display label (optional)"));const lb=mk("input","lb");lb.value=r.label;lb.placeholder=r.tag;d.appendChild(lb);
 d.appendChild(mk("label",null,"Definition"));const df=mk("textarea");df.rows=2;df.value=r.definition;d.appendChild(df);
 if(r.ids.length){const det=mk("details"),sm=mk("summary",null,"Scenarios using it"),ids=mk("div","ids");
  r.ids.forEach(id=>{const a=mk("a",null,id);a.onclick=()=>{tab("scen");show(items.findIndex(x=>x.id===id))};ids.appendChild(a)});
  det.appendChild(sm);det.appendChild(ids);d.appendChild(det)}
 const save=async(regroup)=>{try{await api("/api/category/save",{tag:r.tag,group:gs.value,subgroup:ss.value,label:lb.value,definition:df.value});
  r.definition=df.value;r.label=lb.value;st.textContent="saved ✓";await refreshTax();if(regroup)loadCats()}catch(e){st.textContent="Save failed: "+e.message}};
 lb.onchange=()=>save(false);df.onchange=()=>save(false);ss.onchange=()=>save(true);gs.onchange=()=>{r.subgroup="";fillSubs();save(true)};
 return d}
function renderCats(){const q=$("cfilter").value.toLowerCase(),box=$("clist");box.innerHTML="";
 const rows=cats.rows.filter(r=>!q||(r.tag+" "+r.label+" "+r.group+" "+r.definition).toLowerCase().includes(q));
 $("ccount").textContent=rows.length+" of "+cats.rows.length+" categories";
 [...cats.groups,""].forEach(g=>{const rs=rows.filter(r=>g?r.group===g:!cats.groups.includes(r.group));if(!rs.length)return;
  rs.sort((a,b)=>b.ids.length-a.ids.length||a.tag.localeCompare(b.tag));
  const cls="g-"+(g||"other").toLowerCase(),h=mk("div","gh "+cls);h.style.marginTop="18px";
  h.appendChild(mk("b",null,g||"Ungrouped"));h.appendChild(mk("span",null,rs.length+" categories"));box.appendChild(h);
  const subs_=cats.subgroups.filter(x=>x.group===g);
  rs.filter(r=>!subs_.some(x=>x.name===r.subgroup)).forEach(r=>box.appendChild(catCard(r,cls)));
  subs_.forEach(x=>{const m=rs.filter(r=>r.subgroup===x.name);if(!m.length)return;
   const h2=mk("div","sh",x.name);h2.appendChild(mk("span",null," — "+(x.definition||"(no definition)")));box.appendChild(h2);
   m.forEach(r=>box.appendChild(catCard(r,cls)))})})}
$("cfilter").oninput=()=>cats&&renderCats();
$("casks").onclick=async()=>{const q=$("creq").value.trim();if(!q)return;const b=$("casks");b.disabled=true;b.textContent="Claude is editing files…";
 $("creply").textContent="";$("cdiff").hidden=true;
 try{const dirty=formDirty();const r=await api("/api/categories/ask",{request:q});
  $("creply").textContent="Claude: "+(r.comment||"(done)")+"\nChanged: "+(r.changed.join(", ")||"nothing")+"\nBackup: "+r.backup;
  if(r.diff){$("cdifftxt").textContent=r.diff;$("cdiff").hidden=false}
  $("creq").value="";await reloadAll(dirty);await loadCats()}
 catch(e){$("creply").textContent="Error: "+e.message}
 b.disabled=false;b.textContent="Ask Claude"};
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj, ctype="application/json"):
        data = obj.encode() if isinstance(obj, str) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.reply(200, PAGE, "text/html")
        elif self.path == "/api/state":
            self.reply(200, {"items": state(), **taxonomy()})
        elif self.path == "/api/categories":
            self.reply(200, categories_view())
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            if self.path == "/api/save":
                self.reply(200, save(body))
            elif self.path == "/api/category/save":
                self.reply(200, save_category(body))
            elif self.path == "/api/categories/ask":
                self.reply(200, ask_categories(body))
            elif self.path == "/api/ask":
                self.reply(200, ask_claude(body))
            else:
                self.reply(404, {"error": "not found"})
        except Exception as e:  # surface errors to the UI
            self.reply(500, {"error": f"{type(e).__name__}: {e}"})


def main():
    global OUT_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reviewed.json")
    ap.add_argument("--port", type=int, default=0, help="0 = pick any free port")
    a = ap.parse_args()
    OUT_PATH = os.path.abspath(a.out)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    print(f"Reviewing {len(scs())} scenarios → {OUT_PATH}\n{url}  (Ctrl+C to stop)")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
