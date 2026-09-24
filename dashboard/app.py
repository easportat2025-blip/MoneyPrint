import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, render_template_string, request

import config
import state

try:
    import requests as _rq
except ImportError:
    _rq = None

app = Flask(__name__)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>ReZain - MoneyPrint</title>
<style>
body{font-family:ui-monospace,monospace;background:#0b1020;color:#e6edf3;margin:0;padding:20px}
h1{color:#7ee787;font-size:18px;margin:0 0 4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:12px}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px;min-width:110px}
.card b{font-size:20px;display:block}
.card span{font-size:11px;color:#8b949e}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center}
button,.btn{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:7px 12px;cursor:pointer;font:inherit;font-size:13px}
button:hover{background:#30363d}
button.danger{border-color:#f85149;color:#f85149}
button.warn{border-color:#d29922;color:#d29922}
button.go{border-color:#3fb950;color:#3fb950}
button:disabled{opacity:.4;cursor:default}
select,input{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:7px;font:inherit;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #30363d;padding:8px;text-align:left;vertical-align:top}
th{background:#161b22;color:#7ee787}
tr:nth-child(even){background:#11161d}
.st-done,.st-uploaded{color:#3fb950}.st-failed{color:#f85149}
.st-uploading,.st-rendering,.st-researching,.st-scripting,.st-fetching_media,.st-tts,.st-cleaning,.st-planned{color:#d29922}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;background:#21262d;border:1px solid #30363d;margin:1px;font-size:11px}
.badge.ok{border-color:#3fb950}.badge.no{border-color:#f85149}
a{color:#58a6ff}
.thumb{width:120px;border-radius:4px;display:block}
.err{color:#f85149;max-width:300px;word-break:break-word}
.detail{display:none;background:#0d1117}
.detail td{border-color:#3fb950}
pre{white-space:pre-wrap;font-size:12px;margin:4px 0}
.scene{border-bottom:1px dashed #30363d;padding:6px 0}
.kill-banner{background:#3d1214;border:1px solid #f85149;padding:8px 12px;border-radius:6px;margin-bottom:12px}
h2{color:#7ee787;font-size:15px;margin:20px 0 8px}
.note{color:#8b949e;font-size:12px}
#msg{color:#d29922;font-size:13px;margin-left:8px}
</style></head><body>
<h1>ReZain - MoneyPrint dashboard</h1>
<div class="sub">{{ src }} &middot; synced: {{ synced }} &middot; uploads today: {{ uploads_today }}/{{ max_uploads }}</div>
{% if kill %}<div class="kill-banner">KILL SWITCH ACTIVE (local runs stop)</div>{% endif %}
<div class="stats">
<div class="card"><b>{{ total }}</b><span>records</span></div>
<div class="card"><b style="color:#3fb950">{{ done }}</b><span>uploaded</span></div>
<div class="card"><b>{{ shorts }}</b><span>shorts done</span></div>
<div class="card"><b>{{ longs }}</b><span>long done</span></div>
<div class="card"><b style="color:#f85149">{{ failed }}</b><span>failed</span></div>
<div class="card"><b>{{ rate }}%</b><span>success rate</span></div>
</div>
<div class="toolbar">
<button onclick="go('/sync')">Sync logs</button>
<button onclick="location.reload()">Refresh</button>
<button class="{% if kill %}go{% else %}danger{% endif %}" onclick="go('/kill')">{% if kill %}Unkill{% else %}Kill{% endif %}</button>
<button class="go" id="btnTrig" onclick="go('/trigger')" {% if not has_token %}disabled title="Set GH_TOKEN in local .env to enable"{% endif %}>Run 1 short on GitHub</button>
<button class="warn" onclick="go('/cancel')" {% if not has_token %}disabled title="Set GH_TOKEN in local .env to enable"{% endif %}>Cancel running jobs</button>
<select id="fStatus" onchange="filtr()"><option value="">all status</option><option>done</option><option>failed</option><option>planned</option><option>uploading</option><option>rendering</option></select>
<select id="fKind" onchange="filtr()"><option value="">short+long</option><option value="short">short</option><option value="long">long</option></select>
<input id="fText" placeholder="search title..." oninput="filtr()">
<span id="msg"></span>
</div>
<table id="tbl">
<tr><th></th><th>ID</th><th>Status</th><th>Title</th><th>YouTube</th><th>Stages</th><th>Error</th><th>Updated</th><th></th></tr>
{% for r in records %}
<tr class="row" data-status="{{ r.status }}" data-kind="{{ r.kind }}" data-title="{{ r.title|lower }}">
<td>{% if r.youtube_id %}<a href="{{ r.youtube_url }}" target="_blank"><img class="thumb" src="https://i.ytimg.com/vi/{{ r.youtube_id }}/hqdefault.jpg" loading="lazy"></a>{% endif %}</td>
<td>{{ r.id }}</td>
<td class="st-{{ r.status }}">{{ r.status }}</td>
<td>{{ r.title }}<br><span class="badge">{{ r.kind }}</span></td>
<td>{% if r.youtube_url %}<a href="{{ r.youtube_url }}" target="_blank">open</a>{% else %}—{% endif %}</td>
<td>{% for name, s in (r.stages or {}).items() %}<span class="badge {{ 'ok' if s.ok else 'no' }}" title="{{ s.detail }}">{{ "ok" if s.ok else "x" }} {{ name }}</span>{% endfor %}</td>
<td class="err">{{ r.error[:160] }}</td>
<td>{{ (r.updated_at or "")[:16].replace("T"," ") }}</td>
<td><button onclick="tog('d{{ r.id }}')">detail</button></td>
</tr>
<tr class="detail" id="d{{ r.id }}"><td colspan="9">
<b>Hook:</b> {{ (r.idea or {}).get("hook","") }}<br>
<b>Beats:</b> {{ "; ".join((r.idea or {}).get("beats",[])) }}<br>
<b>Tags:</b> {{ ", ".join((r.idea or {}).get("tags",[])) }}<br>
<b>Created:</b> {{ r.created_at }}<br>
<b>Stages:</b><pre>{{ stages_txt[r.id] }}</pre>
<b>Scenes ({{ (r.scenes or [])|length }}):</b>
{% for s in (r.scenes or []) %}<div class="scene"><b>{{ loop.index }}.</b> {{ s.narration }}<br><span class="note">search: {{ s.search }} | caption: {{ s.caption }}</span></div>{% endfor %}
{% if r.error %}<b>Full error:</b><pre>{{ r.error }}</pre>{% endif %}
</td></tr>
{% endfor %}
</table>
<h2>Idea bank ({{ ideas|length }})</h2>
<table><tr><th>Title</th><th>Hook</th><th>Keywords</th></tr>
{% for i in ideas %}<tr><td>{{ i.title }}</td><td>{{ i.hook }}</td><td>{{ ", ".join(i.get("keywords",[])) }}</td></tr>{% endfor %}
</table>
<p class="note">Kill chi dung local. Muon dung job GitHub dang chay: Cancel running jobs (can GH_TOKEN) hoac vao Actions &gt; Cancel workflow. Token chi de trong .env local, khong commit.</p>
<script>
function filtr(){var s=document.getElementById('fStatus').value,k=document.getElementById('fKind').value,t=document.getElementById('fText').value.toLowerCase();document.querySelectorAll('#tbl tr.row').forEach(function(r){var ok=(!s||r.dataset.status===s)&&(!k||r.dataset.kind===k)&&(!t||r.dataset.title.includes(t));r.style.display=ok?'':'none';});}
function tog(id){var e=document.getElementById(id);e.style.display=e.style.display==='table-row'?'none':'table-row';}
function go(u){document.getElementById('msg').textContent='working...';fetch(u).then(function(r){return r.json();}).then(function(j){document.getElementById('msg').textContent=j.msg||JSON.stringify(j);if(j.ok&&u!=='/kill'){setTimeout(function(){location.reload();},1200);}else if(u==='/kill'){setTimeout(function(){location.reload();},600);}}).catch(function(e){document.getElementById('msg').textContent='error: '+e;});}
</script>
</body></html>"""


def _gh() -> tuple:
    import os

    tok = os.environ.get("GH_TOKEN", "").strip()
    repo = ""
    try:
        p = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        url = p.stdout.strip()
        if "github.com" in url:
            part = url.split("github.com")[1].strip("/: ")
            if part.endswith(".git"):
                part = part[:-4]
            repo = part
    except OSError:
        pass
    return tok, repo


def _gh_api(method: str, path: str, data: dict | None = None) -> dict:
    if _rq is None:
        return {"ok": False, "msg": "requests missing"}
    tok, repo = _gh()
    if not tok or not repo:
        return {"ok": False, "msg": "GH_TOKEN or repo unknown"}
    try:
        r = _rq.request(
            method,
            f"https://api.github.com/repos/{repo}{path}",
            headers={
                "Authorization": f"token {tok}",
                "Accept": "application/vnd.github+json",
            },
            json=data,
            timeout=30,
        )
        if r.status_code in (200, 201, 204):
            return {"ok": True, "msg": "ok", "data": r.json() if r.text else {}}
        return {"ok": False, "msg": f"github {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "msg": str(e)[:200]}


def _source_state() -> tuple[list, str]:
    local = state.load()
    if local:
        return local, "local state.json"
    logs = config.ROOT / "state_from_logs.json"
    if logs.exists():
        try:
            data = json.loads(logs.read_text(encoding="utf-8"))
            if data:
                return data, "state_from_logs.json"
        except json.JSONDecodeError:
            pass
    return [], "empty (Sync first)"


def _ideas() -> list:
    p = config.ROOT / "ideas.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return []


def _synced() -> str:
    p = config.ROOT / "state_from_logs.json"
    if p.exists():
        try:
            import datetime

            ts = p.stat().st_mtime
            return datetime.datetime.fromtimestamp(ts).strftime("%H:%M %d/%m")
        except OSError:
            pass
    return "-"


@app.route("/")
def index():
    records, source = _source_state()
    done = [r for r in records if r.get("status") in ("done", "uploaded")]
    failed = [r for r in records if r.get("status") == "failed"]
    stages_txt = {}
    for r in records:
        lines = []
        for name, s in (r.get("stages") or {}).items():
            mark = "ok" if s.get("ok") else "X"
            lines.append(f"[{mark}] {name} {s.get('at','')} {s.get('detail','')}")
        stages_txt[r["id"]] = "\n".join(lines) or "-"
    total = len(records)
    rate = round(100 * len(done) / total) if total else 0
    tok, _ = _gh()
    return render_template_string(
        PAGE,
        records=records,
        src=source,
        synced=_synced(),
        total=total,
        done=len(done),
        shorts=len([r for r in done if r.get("kind") == "short"]),
        longs=len([r for r in done if r.get("kind") == "long"]),
        failed=len(failed),
        rate=rate,
        stages_txt=stages_txt,
        ideas=_ideas(),
        uploads_today=state.uploads_today(),
        max_uploads=config.MAX_DAILY_UPLOADS,
        kill=config.kill_requested(),
        has_token=bool(tok),
    )


@app.route("/api")
def api():
    records, source = _source_state()
    return jsonify(
        {
            "source": source,
            "uploads_today": state.uploads_today(),
            "kill": config.kill_requested(),
            "records": records,
        }
    )


@app.route("/sync")
def sync():
    p = subprocess.run(["git", "fetch", "origin", "logs"], capture_output=True)
    proc = subprocess.run(
        ["git", "show", "origin/logs:state.json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return jsonify({"ok": False, "msg": "no logs branch state yet"})
    (config.ROOT / "state_from_logs.json").write_text(proc.stdout, encoding="utf-8")
    try:
        n = len(json.loads(proc.stdout))
    except json.JSONDecodeError:
        n = 0
    return jsonify({"ok": True, "msg": f"synced {n} records"})


@app.route("/kill")
def kill():
    if config.KILL_FILE.exists():
        config.KILL_FILE.unlink()
        return jsonify({"ok": True, "kill": False, "msg": "kill OFF"})
    config.KILL_FILE.write_text("1", encoding="utf-8")
    return jsonify({"ok": True, "kill": True, "msg": "kill ON (local only)"})


@app.route("/trigger")
def trigger():
    res = _gh_api(
        "POST",
        "/actions/workflows/shorts.yml/dispatches",
        {"ref": "main", "inputs": {"count": request.args.get("count", "1")}},
    )
    if res["ok"]:
        res["msg"] = "dispatched 1 short on GitHub"
    return jsonify(res)


@app.route("/cancel")
def cancel():
    res = _gh_api("GET", "/actions/runs?per_page=10")
    if not res["ok"]:
        return jsonify(res)
    stopped = 0
    for r in res["data"].get("workflow_runs", []):
        if r.get("status") in ("queued", "in_progress"):
            c = _gh_api("POST", f"/actions/runs/{r['id']}/cancel")
            if c["ok"]:
                stopped += 1
    return jsonify({"ok": True, "msg": f"cancelled {stopped} runs"})


def main():
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
