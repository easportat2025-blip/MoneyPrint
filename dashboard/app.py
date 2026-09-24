import datetime
import json
import subprocess
import sys
import time
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

CRONS = [
    {"job": "Short #1", "utc": "14:00", "vn": "21:00", "wf": "shorts.yml"},
    {"job": "Short #2", "utc": "16:00", "vn": "23:00", "wf": "shorts.yml"},
    {"job": "Short #3", "utc": "18:00", "vn": "01:00+1", "wf": "shorts.yml"},
    {"job": "Long video", "utc": "15:00 /5 ngay", "vn": "22:00 /5 ngay", "wf": "long.yml"},
]

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>ReZain - MoneyPrint</title>
<style>
body{font-family:ui-monospace,monospace;background:#0b1020;color:#e6edf3;margin:0;padding:20px}
h1{color:#7ee787;font-size:18px;margin:0 0 4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:12px}
.tabs{display:flex;gap:6px;margin-bottom:14px}
.tab{background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:8px 8px 0 0;padding:9px 18px;cursor:pointer;font:inherit;font-size:14px;border-bottom:none}
.tab.on{background:#21262d;color:#7ee787;font-weight:bold}
.panel{display:none}.panel.on{display:block}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px 14px;min-width:110px}
.card b{font-size:20px;display:block}
.card span{font-size:11px;color:#8b949e}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;align-items:center}
button{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:7px 12px;cursor:pointer;font:inherit;font-size:13px}
button:hover{background:#30363d}
button.danger{border-color:#f85149;color:#f85149}
button.go{border-color:#3fb950;color:#3fb950}
button.warn{border-color:#d29922;color:#d29922}
button:disabled{opacity:.4;cursor:default}
select,input{background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:7px;font:inherit;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #30363d;padding:8px;text-align:left;vertical-align:top}
th{background:#161b22;color:#7ee787}
tr:nth-child(even){background:#11161d}
.st-done,.st-uploaded{color:#3fb950}.st-failed{color:#f85149}.st-uploading,.st-rendering,.st-researching,.st-scripting,.st-fetching_media,.st-tts,.st-cleaning,.st-planned{color:#d29922}
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
.live-banner{background:#0d2b12;border:1px solid #3fb950;padding:8px 12px;border-radius:6px;margin-bottom:12px}
h2{color:#7ee787;font-size:15px;margin:20px 0 8px}
.note{color:#8b949e;font-size:12px}
#msg{color:#d29922;font-size:13px;margin-left:8px}
.prog{background:#21262d;border-radius:6px;height:18px;overflow:hidden;max-width:420px;margin:4px 0}
.prog>div{background:#3fb950;height:100%;text-align:right;font-size:11px;line-height:18px;padding-right:6px;color:#041}
.prog>div.low{background:#d29922}
.bar-row{display:flex;align-items:flex-end;gap:6px;height:130px;margin:8px 0}
.bar{width:34px;background:#238636;border-radius:4px 4px 0 0;position:relative;min-height:4px}
.bar span{position:absolute;bottom:-20px;left:0;right:0;text-align:center;font-size:10px;color:#8b949e}
.bar b{position:absolute;top:-18px;left:0;right:0;text-align:center;font-size:11px}
.mission{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:10px;max-width:640px}
.mission.done{border-color:#3fb950}
.mission h3{margin:0 0 6px;font-size:14px}
</style></head><body>
<h1>ReZain - MoneyPrint</h1>
<div class="sub">{{ src }} &middot; synced: {{ synced }} &middot; quota: {{ uploads_today }}/{{ max_uploads }}</div>
{% if kill %}<div class="kill-banner">KILL SWITCH ACTIVE (local only)</div>{% endif %}
<div id="liveBox"></div>
<div class="tabs">
<button class="tab on" onclick="tab('videos')">Videos</button>
<button class="tab" onclick="tab('missions')">Missions</button>
<button class="tab" onclick="tab('growth')">Growth + Income</button>
<button class="tab" onclick="tab('plan')">GitHub Plan</button>
</div>

<div class="panel on" id="p-videos">
<div class="stats">
<div class="card"><b>{{ total }}</b><span>records</span></div>
<div class="card"><b style="color:#3fb950">{{ done }}</b><span>uploaded</span></div>
<div class="card"><b>{{ shorts }}</b><span>shorts</span></div>
<div class="card"><b>{{ longs }}</b><span>long</span></div>
<div class="card"><b style="color:#f85149">{{ failed }}</b><span>failed</span></div>
<div class="card"><b>{{ rate }}%</b><span>success</span></div>
</div>
<div class="toolbar">
<button onclick="go('/sync')">Sync logs</button>
<button onclick="location.reload()">Refresh</button>
<button class="{% if kill %}go{% else %}danger{% endif %}" onclick="go('/kill')">{% if kill %}Unkill{% else %}Kill{% endif %}</button>
<button class="go" onclick="trig()" {% if not has_token %}disabled title="GH_TOKEN missing"{% endif %}>Run 1 short</button>
<button class="warn" onclick="go('/cancel')" {% if not has_token %}disabled title="GH_TOKEN missing"{% endif %}>Cancel jobs</button>
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
</div>

<div class="panel" id="p-missions">
<h2>Nhiem vu hom nay ({{ today }})</h2>
<div class="mission {{ 'done' if m.shorts_done>=3 else '' }}">
<h3>3 Shorts/ngay: {{ m.shorts_done }}/3</h3>
<div class="prog"><div class="{{ '' if m.shorts_done>=3 else 'low' }}" style="width:{{ (100*m.shorts_done//3) if m.shorts_done<3 else 100 }}%">{{ m.shorts_done }}/3</div></div>
<div class="note">{% for t in m.shorts_today %}&#10003; {{ t }}<br>{% endfor %}{% if m.shorts_done<3 %}Con thieu {{ 3-m.shorts_done }} video - cron tu chay 21:00 / 23:00 / 01:00 (VN).{% else %}Xong ngay hom nay.{% endif %}</div>
</div>
<div class="mission {{ 'done' if not m.long_due else '' }}">
<h3>Long video /5 ngay: {{ m.long_status }}</h3>
<div class="note">Video dai gan nhat: {{ m.last_long or "chua co" }}. {{ m.long_note }}</div>
</div>
<div class="mission {{ 'done' if m.quota_ok else '' }}">
<h3>Quota YouTube API: {{ m.uploads }}/{{ m.max }} uploads</h3>
<div class="prog"><div class="{{ 'low' if m.uploads>=m.max else '' }}" style="width:{{ 100*m.uploads//m.max }}%">{{ m.uploads }}/{{ m.max }}</div></div>
</div>
</div>

<div class="panel" id="p-growth">
<h2>Kenh (YouTube API that)</h2>
<div class="stats">
<div class="card"><b>{{ ch.subs }}</b><span>subscribers</span></div>
<div class="card"><b>{{ ch.views }}</b><span>total views</span></div>
<div class="card"><b>{{ ch.videos }}</b><span>videos</span></div>
<div class="card"><b>{{ streak }}d</b><span>upload streak</span></div>
</div>
<div class="toolbar"><button onclick="go('/channel?force=1')">Refresh channel stats</button><span class="note">cache 1h, ton 1 unit quota</span></div>
<h2>Upload 14 ngay qua</h2>
<div class="bar-row">{% for d in bars %}<div class="bar" style="height:{{ d.h }}%" title="{{ d.day }}: {{ d.n }}"><b>{{ d.n }}</b><span>{{ d.day[5:] }}</span></div>{% endfor %}</div>
<h2>Thu nhap</h2>
<div class="mission"><h3>Doanh thu uoc tinh: $0</h3>
<div class="note">Chua bat kiem tien. Dieu kien YouTube Partner (Shorts): 1000 subs + 10M Shorts views/90 ngay.<br>
Subs hien tai: {{ ch.subs }} / 1000. Khi du dieu kien, bat monetization trong YouTube Studio &gt; Earn.<br>
Dashboard se tu dong hien so lieu that khi ban ket noi YouTube Analytics API.</div></div>
</div>

<div class="panel" id="p-plan">
<h2>Ke hoach chay tren GitHub (gio VN = UTC+7)</h2>
<table><tr><th>Job</th><th>UTC</th><th>Gio VN</th><th>Workflow</th></tr>
{% for c in crons %}<tr><td>{{ c.job }}</td><td>{{ c.utc }}</td><td>{{ c.vn }}</td><td>{{ c.wf }}</td></tr>{% endfor %}
</table>
<p class="note">Concurrency group <b>moneyprint-video</b>: moi luc chi 1 video chay, job den sau xep hang cho (khong chay song song).<br>
Thoat che do cho: vao Actions &gt; Cancel workflow, hoac nut Cancel jobs tab Videos (can GH_TOKEN).<br>
Trang thai live (dang chay buoc nao) hien o banner xanh tren cung, tu cap nhat moi 30s.</p>
</div>

<p class="note">Kill chi dung local. Token chi trong .env local, khong commit.</p>
<script>
function tab(n){document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on');});document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('on');});event.target.classList.add('on');document.getElementById('p-'+n).classList.add('on');}
function filtr(){var s=document.getElementById('fStatus').value,k=document.getElementById('fKind').value,t=document.getElementById('fText').value.toLowerCase();document.querySelectorAll('#tbl tr.row').forEach(function(r){var ok=(!s||r.dataset.status===s)&&(!k||r.dataset.kind===k)&&(!t||r.dataset.title.includes(t));r.style.display=ok?'':'none';});}
function tog(id){var e=document.getElementById(id);e.style.display=e.style.display==='table-row'?'none':'table-row';}
function go(u){document.getElementById('msg').textContent='working...';fetch(u).then(function(r){return r.json();}).then(function(j){document.getElementById('msg').textContent=j.msg||JSON.stringify(j);setTimeout(function(){location.reload();},1200);}).catch(function(e){document.getElementById('msg').textContent='error: '+e;});}
function trig(){fetch('/live').then(function(r){return r.json();}).then(function(j){var busy=(j.active||[]).length>0;if(busy&&!confirm('Dang co job chay ('+j.active[0].name+'). Van chay them? (se xep hang cho)'))return;go('/trigger');});}
function live(){fetch('/live').then(function(r){return r.json();}).then(function(j){var b=document.getElementById('liveBox');if((j.active||[]).length===0){b.innerHTML='';return;}var h=j.active.map(function(a){return '<div class="live-banner">LIVE: '+a.name+' - '+a.step+' ('+a.elapsed+') <a href="'+a.url+'" target="_blank">xem log</a></div>';}).join('');b.innerHTML=h;}).catch(function(){});}
live();setInterval(live,30000);
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
            ts = p.stat().st_mtime
            return datetime.datetime.fromtimestamp(ts).strftime("%H:%M %d/%m")
        except OSError:
            pass
    return "-"


def _missions(records: list) -> dict:
    today = datetime.date.today().isoformat()
    shorts_today = [
        r.get("title", "")
        for r in records
        if r.get("kind") == "short"
        and r.get("youtube_id")
        and (r.get("created_at", "")[:10] == today)
    ]
    longs = sorted(
        [
            r.get("created_at", "")[:10]
            for r in records
            if r.get("kind") == "long" and r.get("youtube_id")
        ],
        reverse=True,
    )
    last_long = longs[0] if longs else ""
    long_due = True
    long_note = "Chua co long video - cron se chay vao 22:00 (VN) moi 5 ngay."
    if last_long:
        try:
            d = datetime.date.fromisoformat(last_long)
            nxt = d + datetime.timedelta(days=5)
            left = (nxt - datetime.date.today()).days
            if left > 0:
                long_due = False
                long_note = f"Video tiep theo du kien sau {left} ngay ({nxt})."
                long_status = f"con {left} ngay"
            else:
                long_status = "DEN HAN - se chay dot cron toi"
                long_note = "Qua han, cron 22:00 (VN) chu ky 5 ngay se chay."
        except ValueError:
            long_status = "?"
    else:
        long_status = "CHUA CO"
    uploads = state.uploads_today()
    return {
        "shorts_done": len(shorts_today),
        "shorts_today": shorts_today,
        "last_long": last_long,
        "long_due": long_due,
        "long_status": long_status,
        "long_note": long_note,
        "uploads": uploads,
        "max": config.MAX_DAILY_UPLOADS,
        "quota_ok": uploads < config.MAX_DAILY_UPLOADS,
    }


def _bars(records: list) -> list:
    days = [(datetime.date.today() - datetime.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    counts = {d: 0 for d in days}
    for r in records:
        if r.get("youtube_id"):
            d = r.get("created_at", "")[:10]
            if d in counts:
                counts[d] += 1
    mx = max(counts.values()) if counts else 0
    return [
        {"day": d, "n": counts[d], "h": int(100 * counts[d] / mx) if mx else 3}
        for d in days
    ]


def _streak(records: list) -> int:
    days = {r.get("created_at", "")[:10] for r in records if r.get("youtube_id")}
    s = 0
    d = datetime.date.today()
    if d.isoformat() not in days:
        d -= datetime.timedelta(days=1)
    while d.isoformat() in days:
        s += 1
        d -= datetime.timedelta(days=1)
    return s


def channel_stats(force: bool = False) -> dict:
    cache = config.ROOT / "channel_cache.json"
    if not force and cache.exists():
        try:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - d.get("at", 0) < 3600 and d.get("ok"):
                return d
        except (json.JSONDecodeError, OSError):
            pass
    out = {"ok": False, "subs": "-", "views": "-", "videos": "-"}
    if _rq is None:
        return out
    cid, csec, rt = (
        config.YOUTUBE_CLIENT_ID,
        config.YOUTUBE_CLIENT_SECRET,
        config.YOUTUBE_REFRESH_TOKEN,
    )
    if not (cid and rt):
        return out
    try:
        t = _rq.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": csec,
                "refresh_token": rt,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        if t.status_code != 200:
            return out
        token = t.json()["access_token"]
        r = _rq.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"mine": "true", "part": "statistics"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r.status_code != 200:
            return out
        items = r.json().get("items", [])
        if not items:
            return out
        st = items[0].get("statistics", {})
        out = {
            "ok": True,
            "subs": st.get("subscriberCount", "0"),
            "views": st.get("viewCount", "0"),
            "videos": st.get("videoCount", "0"),
            "at": time.time(),
        }
        cache.write_text(json.dumps(out), encoding="utf-8")
    except Exception:
        pass
    return out


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
        today=datetime.date.today().isoformat(),
        total=total,
        done=len(done),
        shorts=len([r for r in done if r.get("kind") == "short"]),
        longs=len([r for r in done if r.get("kind") == "long"]),
        failed=len(failed),
        rate=rate,
        stages_txt=stages_txt,
        ideas=_ideas(),
        m=_missions(records),
        bars=_bars(records),
        streak=_streak(records),
        ch=channel_stats(),
        crons=CRONS,
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


@app.route("/live")
def live():
    res = _gh_api("GET", "/actions/runs?per_page=5")
    if not res["ok"]:
        return jsonify({"ok": False, "active": [], "recent": [], "msg": res["msg"]})
    active, recent = [], []
    for r in res["data"].get("workflow_runs", []):
        info = {
            "id": r["id"],
            "name": r["name"],
            "status": r["status"],
            "conclusion": r.get("conclusion"),
            "url": r.get("html_url", ""),
            "created": (r.get("created_at", "")[11:16]),
        }
        if r.get("status") in ("queued", "in_progress"):
            step, elapsed = "starting...", ""
            try:
                jobs = _gh_api("GET", f"/actions/runs/{r['id']}/jobs")
                if jobs["ok"] and jobs["data"].get("jobs"):
                    j = jobs["data"]["jobs"][0]
                    for s in j.get("steps", []):
                        if s.get("status") == "in_progress":
                            step = s.get("name", "")
                    started = j.get("started_at", "")
                    if started:
                        try:
                            dt = datetime.datetime.fromisoformat(
                                started.replace("Z", "+00:00")
                            )
                            mins = int(
                                (
                                    datetime.datetime.now(datetime.timezone.utc) - dt
                                ).total_seconds()
                                // 60
                            )
                            elapsed = f"{mins} phut"
                        except ValueError:
                            pass
            except Exception:
                pass
            info["step"] = step
            info["elapsed"] = elapsed
            active.append(info)
        else:
            recent.append(info)
    return jsonify({"ok": True, "active": active, "recent": recent[:5]})


@app.route("/channel")
def channel():
    force = request.args.get("force") == "1"
    return jsonify(channel_stats(force=force))


@app.route("/missions")
def missions():
    records, _ = _source_state()
    return jsonify(_missions(records))


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
