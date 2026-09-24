import datetime
import importlib.util
import json
import os
import secrets as pysecrets
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, redirect, render_template_string, request

import config
import state
from pipeline import yt_auth as yt_mod


def _wiz():
    spec = importlib.util.spec_from_file_location(
        "wiz_setup", ROOT / "scripts" / "setup_youtube_auth.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


OAUTH_REDIRECT = "http://127.0.0.1:5050/oauth/callback"
OAUTH_SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload"
    " https://www.googleapis.com/auth/youtube.readonly"
)
_oauth_states: dict = {}

try:
    import requests as _rq
except ImportError:
    _rq = None

app = Flask(__name__)

CRONS = [
    {"job": "Acc1 Short #1", "utc": "16:00", "vn": "23:00 VN / 12:00 ET", "wf": "shorts-acc1.yml"},
    {"job": "Acc1 Short #2", "utc": "19:00", "vn": "02:00 VN / 15:00 ET", "wf": "shorts-acc1.yml"},
    {"job": "Acc1 Short #3", "utc": "22:00", "vn": "05:00 VN / 18:00 ET", "wf": "shorts-acc1.yml"},
    {"job": "Acc2 Short #1", "utc": "17:30", "vn": "00:30 VN / 13:30 ET", "wf": "shorts-acc2.yml"},
    {"job": "Acc2 Short #2", "utc": "20:30", "vn": "03:30 VN / 16:30 ET", "wf": "shorts-acc2.yml"},
    {"job": "Acc2 Short #3", "utc": "23:30", "vn": "06:30 VN / 19:30 ET", "wf": "shorts-acc2.yml"},
    {"job": "Acc1 Long", "utc": "15:00 /5 ngay", "vn": "22:00 VN /5 ngay", "wf": "long.yml"},
]

SHORTS_TARGET = 3
ALLOWED_WF = {"shorts-acc1": "shorts-acc1.yml", "shorts-acc2": "shorts-acc2.yml", "long": "long.yml"}

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MoneyPrint Studio</title>
<style>
:root{--bg:#0a0e1a;--bg2:#111630;--card:#151b3d;--line:#2a3160;--txt:#eef1ff;--mut:#9aa3c7;--acc:#7c6cff;--acc2:#00d4ff;--grn:#22c55e;--red:#ef4444;--yel:#f59e0b}
*{box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:radial-gradient(1200px 400px at 20% -10%,#1c2456 0%,var(--bg) 60%);color:var(--txt);margin:0;min-height:100vh}
.nav{position:sticky;top:0;z-index:5;background:rgba(10,14,26,.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:12px 22px;display:flex;align-items:center;gap:14px}
.logo{font-weight:800;font-size:18px;background:linear-gradient(90deg,var(--acc),var(--acc2));-webkit-background-clip:text;background-clip:text;color:transparent}
.logo small{font-size:11px;color:var(--mut);font-weight:400;display:block;-webkit-text-fill-color:var(--mut)}
.tabs{display:flex;gap:6px;margin-left:8px;flex-wrap:wrap}
.tab{background:transparent;border:1px solid transparent;color:var(--mut);border-radius:999px;padding:8px 16px;cursor:pointer;font:inherit;font-size:13.5px;font-weight:600}
.tab:hover{color:var(--txt)}
.tab.on{background:linear-gradient(90deg,var(--acc),#5a4de0);color:#fff;box-shadow:0 4px 18px rgba(124,108,255,.4)}
.wrap{padding:20px 22px;max-width:1200px;margin:0 auto}
.sub{color:var(--mut);font-size:12px;margin:2px 0 14px}
.panel{display:none}.panel.on{display:block;animation:fade .25s}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.card{background:linear-gradient(180deg,var(--card),#10153a);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.card b{font-size:24px;display:block}
.card span{font-size:11.5px;color:var(--mut)}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
button{background:#1d2450;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:8px 14px;cursor:pointer;font:inherit;font-size:13px;font-weight:600}
button:hover{border-color:var(--acc)}
button.primary{background:linear-gradient(90deg,var(--acc),#5a4de0);border:none;box-shadow:0 4px 16px rgba(124,108,255,.35)}
button.danger{border-color:var(--red);color:#ff8a8a}
button.go{border-color:var(--grn);color:#7dffa8}
button.warn{border-color:var(--yel);color:#ffd47d}
button.big{font-size:16px;padding:14px 26px;border-radius:14px;width:100%}
button:disabled{opacity:.35;cursor:default}
select,input{background:#0d1230;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:8px;font:inherit;font-size:13px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}
th{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
tr.row:hover{background:rgba(124,108,255,.06)}
.st-done,.st-uploaded{color:var(--grn);font-weight:700}.st-failed{color:var(--red);font-weight:700}
.st-uploading,.st-rendering,.st-researching,.st-scripting,.st-fetching_media,.st-tts,.st-cleaning,.st-planned,.st-mixing_music{color:var(--yel)}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;background:#1d2450;border:1px solid var(--line);margin:1px;font-size:11px}
.badge.ok{border-color:var(--grn);color:#7dffa8}.badge.no{border-color:var(--red);color:#ff8a8a}
a{color:var(--acc2)}
.thumb{width:120px;border-radius:10px;display:block}
.err{color:#ff8a8a;max-width:300px;word-break:break-word;font-size:12px}
.detail{display:none;background:#0d1230}
pre{white-space:pre-wrap;font-size:12px;margin:4px 0;background:#0a0e24;padding:8px;border-radius:8px}
.scene{border-bottom:1px dashed var(--line);padding:6px 0}
.kill-banner{background:rgba(239,68,68,.12);border:1px solid var(--red);padding:10px 14px;border-radius:12px;margin-bottom:12px}
.live-banner{background:rgba(34,197,94,.1);border:1px solid var(--grn);padding:10px 14px;border-radius:12px;margin-bottom:12px}
h2{font-size:15px;margin:22px 0 10px}
.note{color:var(--mut);font-size:12px}
#msg{color:var(--yel);font-size:13px;margin-left:8px}
.prog{background:#1d2450;border-radius:999px;height:20px;overflow:hidden;max-width:460px;margin:6px 0}
.prog>div{background:linear-gradient(90deg,var(--grn),#4ade80);height:100%;text-align:right;font-size:11px;line-height:20px;padding-right:8px;color:#041;font-weight:700}
.prog>div.low{background:linear-gradient(90deg,var(--yel),#fbbf24)}
.bar-row{display:flex;align-items:flex-end;gap:8px;height:140px;margin:10px 0 26px}
.bar{width:36px;background:linear-gradient(180deg,var(--acc),#4a3fd4);border-radius:6px 6px 0 0;position:relative;min-height:4px}
.bar span{position:absolute;bottom:-20px;left:0;right:0;text-align:center;font-size:10px;color:var(--mut)}
.bar b{position:absolute;top:-18px;left:0;right:0;text-align:center;font-size:11px}
.mission{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px;max-width:680px}
.mission.done{border-color:var(--grn)}
.mission h3{margin:0 0 6px;font-size:14px}
.force-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.force-card{background:linear-gradient(180deg,var(--card),#10153a);border:1px solid var(--line);border-radius:16px;padding:20px}
.force-card h3{margin:0 0 4px;font-size:16px}
.force-card p{color:var(--mut);font-size:12.5px;margin:4px 0 14px}
.acct{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.dot{width:12px;height:12px;border-radius:50%;background:var(--mut)}
.dot.ok{background:var(--grn);box-shadow:0 0 10px var(--grn)}
.dot.bad{background:var(--red)}
</style></head><body>
<div class="nav"><div class="logo">MoneyPrint<small>faceless video studio</small></div>
<div class="tabs">
<button class="tab on" onclick="tab('videos',this)">Videos</button>
<button class="tab" onclick="tab('force',this)">Force Make</button>
<button class="tab" onclick="tab('missions',this)">Missions</button>
<button class="tab" onclick="tab('growth',this)">Growth + Income</button>
<button class="tab" onclick="tab('plan',this)">GitHub Plan</button>
<button class="tab" onclick="tab('accounts',this)">Accounts</button>
</div></div>
<div class="wrap">
<div class="sub">{{ src }} &middot; synced {{ synced }} &middot; quota {{ uploads_today }}/{{ max_uploads }}</div>
{% if kill %}<div class="kill-banner">KILL SWITCH ACTIVE (local only)</div>{% endif %}
<div id="liveBox"></div>

<div class="panel on" id="p-videos">
<div class="grid">
<div class="card"><b>{{ total }}</b><span>records</span></div>
<div class="card"><b style="color:var(--grn)">{{ done }}</b><span>uploaded</span></div>
<div class="card"><b>{{ shorts }}</b><span>shorts</span></div>
<div class="card"><b>{{ longs }}</b><span>long</span></div>
<div class="card"><b style="color:var(--red)">{{ failed }}</b><span>failed</span></div>
<div class="card"><b>{{ rate }}%</b><span>success</span></div>
</div>
<div class="toolbar">
<button onclick="go('/sync')">Sync logs</button>
<button onclick="location.reload()">Refresh</button>
<button class="{% if kill %}go{% else %}danger{% endif %}" onclick="go('/kill')">{% if kill %}Unkill{% else %}Kill{% endif %}</button>
<button class="warn" onclick="go('/cancel')" {% if not has_token %}disabled title="GH_TOKEN missing"{% endif %}>Cancel jobs</button>
<select id="fStatus" onchange="filtr()"><option value="">all status</option><option>done</option><option>failed</option><option>planned</option><option>uploading</option><option>rendering</option></select>
<select id="fKind" onchange="filtr()"><option value="">short+long</option><option value="short">short</option><option value="long">long</option></select>
<select id="fCh" onchange="filtr()"><option value="">all channels</option>{% for c in ch_names %}<option>{{ c }}</option>{% endfor %}</select>
<input id="fText" placeholder="search title..." oninput="filtr()">
<span id="msg"></span>
</div>
<table id="tbl">
<tr><th></th><th>ID</th><th>Status</th><th>Title</th><th>YouTube</th><th>Stages</th><th>Error</th><th>Updated</th><th></th></tr>
{% for r in records %}
<tr class="row" data-status="{{ r.status }}" data-kind="{{ r.kind }}" data-title="{{ r.title|lower }}" data-ch="{{ r.channel or '' }}">
<td>{% if r.youtube_id %}<a href="{{ r.youtube_url }}" target="_blank"><img class="thumb" src="https://i.ytimg.com/vi/{{ r.youtube_id }}/hqdefault.jpg" loading="lazy"></a>{% endif %}</td>
<td>{{ r.id }}</td>
<td class="st-{{ r.status }}">{{ r.status }}</td>
<td>{{ r.title }}<br><span class="badge">{{ r.kind }}</span> <span class="badge">{{ r.channel or "?" }}</span></td>
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

<div class="panel" id="p-force">
<h2 style="margin-top:0">Force make video – chay ngay tren GitHub</h2>
<p class="note">Moi luc 1 video (concurrency group). Bam khi job khac dang chay = xep hang cho. Khong can cho cron.</p>
<div class="force-grid">
<div class="force-card"><div class="acct"><div class="dot {{ 'ok' if acc1_ok else 'bad' }}"></div><h3>Acc 1 – {{ acc1_name }}</h3></div>
<p>1 Short doc (~12 phut): plan → voice → clips → subs → upload public. Hom nay: {{ amap1.done }}/3.</p>
<button class="primary big" onclick="trig('shorts-acc1')" {% if not has_token %}disabled{% endif %}>Force 1 Short – Acc 1</button></div>
<div class="force-card"><div class="acct"><div class="dot {{ 'ok' if acc2_ok else 'bad' }}"></div><h3>Acc 2 – {{ acc2_name }}</h3></div>
<p>1 Short kenh 2. Hom nay: {{ amap2.done }}/3. Can token slot 2 (chua co = nut mo).</p>
<button class="primary big" onclick="trig('shorts-acc2')" {% if not has_token %}disabled{% endif %}>Force 1 Short – Acc 2</button></div>
<div class="force-card"><div class="acct"><div class="dot ok"></div><h3>Long video – Acc 1</h3></div>
<p>1 video &gt;5 phut ngang (~30-60 phut render). Chay thua, khong gap.</p>
<button class="big" onclick="trig('long')" {% if not has_token %}disabled{% endif %}>Force 1 Long</button></div>
</div>
<p><span id="msgF" class="note"></span></p>
</div>

<div class="panel" id="p-missions">
<h2 style="margin-top:0">Nhiem vu hom nay ({{ today }})</h2>
{% for ch in channels %}
<div class="mission {{ 'done' if ch.done>=3 else '' }}">
<h3>{{ ch.name }}: {{ ch.done }}/3 shorts</h3>
<div class="prog"><div class="{{ '' if ch.done>=3 else 'low' }}" style="width:{{ (100*ch.done//3) if ch.done<3 else 100 }}%">{{ ch.done }}/3</div></div>
<div class="note">{% for t in ch.titles %}&#10003; {{ t }}<br>{% endfor %}{% if ch.done<3 %}Con thieu {{ 3-ch.done }} video.{% else %}Xong.{% endif %}</div>
</div>
{% endfor %}
<div class="mission {{ 'done' if not m.long_due else '' }}">
<h3>Long video /5 ngay: {{ m.long_status }}</h3>
<div class="note">Gan nhat: {{ m.last_long or "chua co" }}. {{ m.long_note }}</div>
</div>
<div class="mission {{ 'done' if m.quota_ok else '' }}">
<h3>Quota YouTube API: {{ m.uploads }}/{{ m.max }}</h3>
<div class="prog"><div class="{{ 'low' if m.uploads>=m.max else '' }}" style="width:{{ 100*m.uploads//m.max }}%">{{ m.uploads }}/{{ m.max }}</div></div>
</div>
</div>

<div class="panel" id="p-growth">
<h2 style="margin-top:0">Kenh (YouTube API that)</h2>
<div class="grid">
<div class="card"><b>{{ ch.subs }}</b><span>subscribers</span></div>
<div class="card"><b>{{ ch.views }}</b><span>total views</span></div>
<div class="card"><b>{{ ch.videos }}</b><span>videos</span></div>
<div class="card"><b>{{ streak }}d</b><span>upload streak</span></div>
</div>
<div class="toolbar"><button onclick="go('/channel?force=1')">Refresh channel stats</button><span class="note">cache 1h, ton 1 unit</span></div>
<h2>Upload 14 ngay qua</h2>
<div class="bar-row">{% for d in bars %}<div class="bar" style="height:{{ d.h }}%" title="{{ d.day }}: {{ d.n }}"><b>{{ d.n }}</b><span>{{ d.day[5:] }}</span></div>{% endfor %}</div>
<h2>Thu nhap</h2>
<div class="mission"><h3>Doanh thu uoc tinh: $0</h3>
<div class="note">Chua bat kiem tien. Dieu kien Partner (Shorts): 1000 subs + 10M Shorts views/90 ngay.<br>
Subs: {{ ch.subs }} / 1000. Du dieu kien thi bat trong YouTube Studio &gt; Earn.</div></div>
</div>

<div class="panel" id="p-plan">
<h2 style="margin-top:0">Ke hoach GitHub (gio VN = UTC+7)</h2>
<table><tr><th>Job</th><th>UTC</th><th>Gio dia phuong</th><th>Workflow</th></tr>
{% for c in crons %}<tr><td>{{ c.job }}</td><td>{{ c.utc }}</td><td>{{ c.vn }}</td><td>{{ c.wf }}</td></tr>{% endfor %}
</table>
<p class="note">Concurrency <b>moneyprint-video</b>: 1 video/luc, job sau xep hang.<br>
Ping chinh xac: dung <b>worker-ping.js</b> (Cloudflare) thay cron – xem README.<br>
Live status tu cap nhat moi 30s o banner xanh.</p>
</div>

<div class="panel" id="p-accounts">
<div class="toolbar">
<button class="primary" onclick="window.open('/login?slot=1','_blank')">Dang nhap Google acc 1</button>
<span class="note">dung mail: <b>{{ acc1_email }}</b></span>
<button class="primary" onclick="window.open('/login?slot=2','_blank')">Dang nhap Google acc 2</button>
<span class="note">dung mail: <b>{{ acc2_email }}</b></span>
<button onclick="window.open('/gcp','_blank')">Tao Client ID</button>
<button onclick="goAcc()">Check lai login</button>
<span id="msgAcc" class="note"></span>
</div>
{% for a in accs %}
<div class="mission {{ 'done' if a.readonly_ok else '' }}">
<h3>Slot {{ a.slot }} – {{ a.name }} &lt;{{ a.email }}&gt;
{% if a.readonly_ok %}<span class="badge ok">LOGGED IN</span>
{% elif a.token_ok %}<span class="badge">TOKEN OK / thieu scope</span>
{% elif a.configured %}<span class="badge no">TOKEN DIE</span>
{% else %}<span class="badge">CHUA CAI</span>{% endif %}</h3>
{% if a.channel_title %}<div>Kenh: <a href="https://www.youtube.com/channel/{{ a.channel_id }}" target="_blank">{{ a.channel_title }}</a></div>{% endif %}
<div class="grid">
<div class="card"><b>{{ a.subs }}</b><span>subs</span></div>
<div class="card"><b>{{ a.videos }}</b><span>videos</span></div>
<div class="card"><b>{{ amap[a.slot].done }}/3</b><span>shorts hom nay</span></div>
</div>
{% if a.error %}<div class="err">{{ a.error }}</div>{% endif %}
<div class="note">Login lai: nut Dang nhap o tren (chon dung mail) &rarr; copy token vao .env + Secrets. Thu hoi: <a href="https://myaccount.google.com/permissions" target="_blank">myaccount.google.com/permissions</a></div>
</div>
{% endfor %}
</div>

<p class="note">Kill chi dung local. Token chi trong .env local, khong commit.</p>
</div>
<script>
function tab(n,el){document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('on');});document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('on');});el.classList.add('on');document.getElementById('p-'+n).classList.add('on');}
function filtr(){var s=document.getElementById('fStatus').value,k=document.getElementById('fKind').value,c=document.getElementById('fCh').value,t=document.getElementById('fText').value.toLowerCase();document.querySelectorAll('#tbl tr.row').forEach(function(r){var ok=(!s||r.dataset.status===s)&&(!k||r.dataset.kind===k)&&(!c||r.dataset.ch===c)&&(!t||r.dataset.title.includes(t));r.style.display=ok?'':'none';});}
function tog(id){var e=document.getElementById(id);e.style.display=e.style.display==='table-row'?'none':'table-row';}
function go(u){document.getElementById('msg').textContent='working...';fetch(u).then(function(r){return r.json();}).then(function(j){document.getElementById('msg').textContent=j.msg||JSON.stringify(j);setTimeout(function(){location.reload();},1200);}).catch(function(e){document.getElementById('msg').textContent='error: '+e;});}
function goAcc(){document.getElementById('msgAcc').textContent='checking...';fetch('/accounts?force=1').then(function(r){return r.json();}).then(function(j){setTimeout(function(){location.reload();},800);}).catch(function(e){document.getElementById('msgAcc').textContent='error: '+e;});}
function trig(wf){fetch('/live').then(function(r){return r.json();}).then(function(j){var busy=(j.active||[]).length>0;var label=wf==='long'?'Long video':(wf==='shorts-acc2'?'Acc 2':'Acc 1');if(busy&&!confirm('Dang co job chay ('+j.active[0].name+' - '+j.active[0].step+'). Force '+label+' se XEP HANG cho. Tiep tuc?'))return;document.getElementById('msgF').textContent='dang kich chay '+label+'...';fetch('/trigger?wf='+wf).then(function(r){return r.json();}).then(function(k){document.getElementById('msgF').textContent=k.msg||JSON.stringify(k);});});}
function live(){fetch('/live').then(function(r){return r.json();}).then(function(j){var b=document.getElementById('liveBox');if((j.active||[]).length===0){b.innerHTML='';return;}b.innerHTML=j.active.map(function(a){return '<div class="live-banner">LIVE: '+a.name+' – '+a.step+' ('+a.elapsed+') <a href="'+a.url+'" target="_blank">xem log</a></div>';}).join('');}).catch(function(){});}
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


def _channel_missions(records: list, channel: str) -> dict:
    today = datetime.date.today().isoformat()
    shorts_today = [
        r.get("title", "")
        for r in records
        if r.get("kind") == "short"
        and (r.get("channel") or "") == channel
        and r.get("youtube_id")
        and (r.get("created_at", "")[:10] == today)
    ]
    return {"name": channel, "done": len(shorts_today), "titles": shorts_today}


def _missions(records: list) -> dict:
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
    ch_names = sorted({r.get("channel") or "?" for r in records})
    if not ch_names:
        ch_names = [config.CHANNEL_1_NAME, config.CHANNEL_2_NAME]
    channels = [_channel_missions(records, c) for c in ch_names]
    accs = yt_mod.check_all()
    done_by_name = {c["name"]: c["done"] for c in channels}
    amap = {a["slot"]: {"done": done_by_name.get(a["name"], 0)} for a in accs}
    acc1 = next((a for a in accs if a["slot"] == "1"), {})
    acc2 = next((a for a in accs if a["slot"] == "2"), {})
    acc1_email = os.environ.get("ACCOUNT_1_EMAIL", "").strip() or "mail chu kenh 1"
    acc2_email = os.environ.get("ACCOUNT_2_EMAIL", "").strip() or "mail chu kenh 2"
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
        channels=channels,
        ch_names=ch_names,
        accs=accs,
        amap=amap,
        acc1_email=acc1_email,
        acc2_email=acc2_email,
        acc1_name=config.CHANNEL_1_NAME,
        acc2_name=config.CHANNEL_2_NAME,
        ch=channel_stats(),
        acc1_ok=bool(acc1.get("readonly_ok")),
        acc2_ok=bool(acc2.get("readonly_ok")),
        amap1=amap.get("1", {"done": 0}),
        amap2=amap.get("2", {"done": 0}),
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
    wf = request.args.get("wf", "shorts-acc1")
    if wf not in ALLOWED_WF:
        return jsonify({"ok": False, "msg": f"unknown wf (chon {list(ALLOWED_WF)})"})
    res = _gh_api(
        "POST",
        f"/actions/workflows/{ALLOWED_WF[wf]}/dispatches",
        {"ref": "main", "inputs": {"count": request.args.get("count", "1")}},
    )
    if res["ok"]:
        res["msg"] = f"dispatched {wf} on GitHub"
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


@app.route("/accounts")
def accounts():
    force = request.args.get("force") == "1"
    return jsonify({"accounts": yt_mod.check_all(force=force)})


@app.route("/gcp")
def gcp():
    return redirect("https://console.cloud.google.com/apis/credentials")


@app.route("/login")
def login():
    slot = request.args.get("slot", "1")
    if slot not in ("1", "2"):
        slot = "1"
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    if not cid:
        return (
            "<h3>Thieu YOUTUBE_CLIENT_ID trong .env</h3>"
            "<p>Bam nut <b>Tao Client ID</b>, tao Desktop client, "
            "paste ID + Secret vao .env roi bam Dang nhap lai.</p>",
            400,
        )
    rnd = pysecrets.token_urlsafe(16)
    _oauth_states[rnd] = slot
    want = os.environ.get(f"ACCOUNT_{slot}_EMAIL", "").strip()
    want_html = f"<b style='color:green'>{want}</b>" if want else "(mail chu kenh)"
    go = f"/login/go?st={rnd}"
    return (
        f"<h3>Dang nhap Google – acc {slot}</h3>"
        f"<p>Buoc toi Google se hoi chon tai khoan. <b>BAT BUOC chon dung mail:</b><br>{want_html}</p>"
        f"<p>Chon sai mail = loi 403 access_denied.</p>"
        f"<p><a href='{go}'><button style='padding:10px 24px;font-size:15px'>Tiep tuc sang Google</button></a></p>"
    )


@app.route("/login/go")
def login_go():
    rnd = request.args.get("st", "")
    slot = _oauth_states.get(rnd)
    if slot is None:
        return "<h3>Phien het han</h3><p>Dong tab, bam Dang nhap lai.</p>", 400
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": cid,
            "redirect_uri": OAUTH_REDIRECT,
            "response_type": "code",
            "scope": OAUTH_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": f"{slot}.{rnd}",
        }
    )
    return redirect(url)


@app.route("/oauth/callback")
def oauth_callback():
    if request.args.get("error"):
        return (
            "<h3>Ban da tu choi hoac co loi</h3><p>Dong tab, bam Dang nhap lai.</p>",
            400,
        )
    code = request.args.get("code", "")
    st = request.args.get("state", "")
    slot, _, rnd = st.partition(".")
    if slot not in ("1", "2") or _oauth_states.pop(rnd, None) != slot or not code:
        return "<h3>Phien het han</h3><p>Dong tab, bam Dang nhap lai tu dashboard.</p>", 400
    if _rq is None:
        return "<h3>Thieu requests</h3>", 500
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    csec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    r = _rq.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": cid,
            "client_secret": csec,
            "redirect_uri": OAUTH_REDIRECT,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if r.status_code != 200:
        hint = ""
        if "redirect_uri_mismatch" in r.text:
            hint = "<p><b>Loi redirect_uri_mismatch:</b> client phai la loai <b>Desktop app</b>, khong phai Web. Tao lai client Desktop.</p>"
        return f"<h3>Doi token that bai ({r.status_code})</h3>{hint}<pre>{r.text[:400]}</pre>", 400
    rt = r.json().get("refresh_token", "")
    if not rt:
        return (
            "<h3>Google khong tra refresh_token</h3><p>Vao "
            "<a href='https://myaccount.google.com/permissions'>myaccount.google.com/permissions</a> "
            "go quyen app, roi Dang nhap lai.</p>",
            400,
        )
    key = "YOUTUBE_REFRESH_TOKEN" if slot == "1" else "YOUTUBE_REFRESH_TOKEN_2"
    wiz = _wiz()
    env = wiz.read_env()
    env[key] = rt
    wiz.write_env(env)
    os.environ[key] = rt
    try:
        yt_mod._cache_path(slot).unlink(missing_ok=True)
    except OSError:
        pass
    return (
        f"<h3 style='color:green'>Dang nhap acc {slot} XONG</h3>"
        f"<p>Refresh token da tu ghi vao <b>.env</b> ({key}). Cuoi buoc:</p>"
        f"<p>Copy dong nay vao GitHub <b>Secrets</b> (ten <b>{key}</b>):</p>"
        f"<textarea rows='3' cols='90' readonly>{rt}</textarea>"
        f"<p>Xong dong tab, ve dashboard tab Accounts bam <b>Check lai login</b>.</p>"
    )


def main():
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
