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
    {"job": "Acc1 Short #1", "utc": "16:00", "ch": "ReZain", "wf": "shorts-acc1.yml"},
    {"job": "Acc1 Short #2", "utc": "19:00", "ch": "ReZain", "wf": "shorts-acc1.yml"},
    {"job": "Acc1 Short #3", "utc": "22:00", "ch": "ReZain", "wf": "shorts-acc1.yml"},
    {"job": "Acc2 Short #1", "utc": "17:30", "ch": "Channel2", "wf": "shorts-acc2.yml"},
    {"job": "Acc2 Short #2", "utc": "20:30", "ch": "Channel2", "wf": "shorts-acc2.yml"},
    {"job": "Acc2 Short #3", "utc": "23:30", "ch": "Channel2", "wf": "shorts-acc2.yml"},
    {"job": "Acc1 Long (/5d)", "utc": "15:00", "ch": "ReZain", "wf": "long.yml"},
]

SHORTS_TARGET = 3
ALLOWED_WF = {"shorts-acc1": "shorts-acc1.yml", "shorts-acc2": "shorts-acc2.yml", "long": "long.yml"}
VIEWS_FILE = ROOT / "views_history.json"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MoneyPrint Studio</title>
<style>
:root{--bg:#0c1210;--side:#101713;--card:#141d18;--card2:#182420;--line:#223028;--txt:#e8f0ea;--mut:#93a89a;--mint:#a9f0c6;--mint-d:#5ecf8f;--grn:#34d399;--red:#f87171;--yel:#fbbf24}
*{box-sizing:border-box}
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--txt);margin:0;font-size:15px;display:flex;min-height:100vh}
.side{width:248px;flex-shrink:0;background:var(--side);border-right:1px solid var(--line);padding:18px 14px;display:flex;flex-direction:column;gap:6px;position:sticky;top:0;height:100vh}
.logo{font-weight:800;font-size:19px;display:flex;align-items:center;gap:8px;padding:2px 6px 14px}
.logo .mk{width:26px;height:26px;border-radius:8px;background:linear-gradient(135deg,var(--mint),var(--mint-d));display:inline-flex;align-items:center;justify-content:center;color:#06281a;font-weight:900}
.logo small{color:var(--mut);font-weight:400}
.create{background:var(--mint);color:#06281a;border:none;border-radius:12px;padding:12px;font:inherit;font-weight:700;font-size:14.5px;cursor:pointer;margin-bottom:14px}
.create:hover{filter:brightness(1.06)}
.ws{font-size:11px;letter-spacing:1.5px;color:var(--mut);padding:6px 10px 4px}
.ws-acc{display:flex;align-items:center;gap:9px;padding:9px 10px;border-radius:10px;cursor:pointer;font-size:13.5px}
.ws-acc:hover{background:var(--card)}
.ws-acc .av{width:26px;height:26px;border-radius:50%;background:#23402f;display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--mint)}
.dot{width:9px;height:9px;border-radius:50%;background:var(--mut);margin-left:auto}
.dot.ok{background:var(--grn);box-shadow:0 0 8px var(--grn)}
.dot.bad{background:var(--red)}
.navbtn{display:flex;align-items:center;gap:11px;background:transparent;border:none;color:var(--mut);border-radius:10px;padding:10px 12px;cursor:pointer;font:inherit;font-size:14px;width:100%;text-align:left}
.navbtn:hover{color:var(--txt);background:var(--card)}
.navbtn.on{background:#1b2b22;color:var(--mint);border-left:3px solid var(--mint-d)}
.navbtn .ic{width:20px;text-align:center}
.user{margin-top:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;font-size:12.5px;display:flex;gap:9px;align-items:center}
.user .av{width:28px;height:28px;border-radius:50%;background:#23402f;display:inline-flex;align-items:center;justify-content:center;font-weight:700;color:var(--mint)}
.user small{color:var(--mut);display:block}
.main{flex:1;padding:26px 30px;max-width:1150px}
.sub{color:var(--mut);font-size:12.5px;margin:2px 0 16px}
.panel{display:none}.panel.on{display:block;animation:fade .25s}
@keyframes fade{from{opacity:0;transform:translateY(6px)}to{opacity:1}}
.hero{background:linear-gradient(180deg,var(--card2),var(--card));border:1px solid var(--line);border-radius:18px;padding:24px 26px;margin-bottom:18px}
.hero h1{margin:0 0 4px;font-size:26px}
.hero p{color:var(--mut);margin:0 0 16px;font-size:14px}
.hero .row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.pill{border:1px solid var(--line);border-radius:999px;padding:6px 14px;font-size:12.5px;color:var(--mut)}
.pill.ok{color:var(--mint);border-color:var(--mint-d)}
.bigstat{font-size:22px;font-weight:800;margin:14px 0 2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.card b{font-size:23px;display:block}
.card span{font-size:11.5px;color:var(--mut)}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center}
button{background:#1a2620;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:8px 14px;cursor:pointer;font:inherit;font-size:13.5px;font-weight:600}
button:hover{border-color:var(--mint-d)}
button.primary{background:var(--mint);color:#06281a;border:none}
button.danger{border-color:var(--red);color:#fca5a5}
button.go{border-color:var(--grn);color:#a7f3d0}
button.warn{border-color:var(--yel);color:#fde68a}
button.big{font-size:16px;padding:14px 26px;border-radius:14px;width:100%}
button:disabled{opacity:.35;cursor:default}
select,input{background:#0e1512;color:var(--txt);border:1px solid var(--line);border-radius:10px;padding:8px;font:inherit;font-size:13.5px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{border-bottom:1px solid var(--line);padding:9px;text-align:left;vertical-align:top}
th{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px}
tr.row:hover{background:rgba(169,240,198,.05)}
.st-done,.st-uploaded{color:var(--grn);font-weight:700}.st-failed{color:var(--red);font-weight:700}
.st-uploading,.st-rendering,.st-researching,.st-scripting,.st-fetching_media,.st-tts,.st-cleaning,.st-planned,.st-mixing_music{color:var(--yel)}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;background:#1a2620;border:1px solid var(--line);margin:1px;font-size:11px}
.badge.ok{border-color:var(--grn);color:#a7f3d0}.badge.no{border-color:var(--red);color:#fca5a5}
a{color:#7dd3fc}
.thumb{width:120px;border-radius:10px;display:block}
.err{color:#fca5a5;max-width:300px;word-break:break-word;font-size:12px}
.detail{display:none;background:#0d1310}
pre{white-space:pre-wrap;font-size:12px;margin:4px 0;background:#0a0f0c;padding:8px;border-radius:8px}
.scene{border-bottom:1px dashed var(--line);padding:6px 0}
.kill-banner{background:rgba(248,113,113,.1);border:1px solid var(--red);padding:10px 14px;border-radius:12px;margin-bottom:12px}
.live-banner{background:rgba(52,211,153,.08);border:1px solid var(--grn);padding:10px 14px;border-radius:12px;margin-bottom:12px}
h2{font-size:15.5px;margin:22px 0 10px}
.note{color:var(--mut);font-size:12.5px}
#msg{color:var(--yel);font-size:13px;margin-left:8px}
.prog{background:#1a2620;border-radius:999px;height:20px;overflow:hidden;max-width:460px;margin:6px 0}
.prog>div{background:linear-gradient(90deg,var(--mint-d),var(--mint));height:100%;text-align:right;font-size:11px;line-height:20px;padding-right:8px;color:#06281a;font-weight:700}
.prog>div.low{background:linear-gradient(90deg,var(--yel),#fcd34d)}
.bar-row{display:flex;align-items:flex-end;gap:8px;height:140px;margin:10px 0 26px}
.bar{width:36px;background:linear-gradient(180deg,var(--mint-d),#2f7d55);border-radius:6px 6px 0 0;position:relative;min-height:4px}
.bar span{position:absolute;bottom:-20px;left:0;right:0;text-align:center;font-size:10px;color:var(--mut)}
.bar b{position:absolute;top:-18px;left:0;right:0;text-align:center;font-size:11px}
.mission{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px;margin-bottom:12px;max-width:700px}
.mission.done{border-color:var(--mint-d)}
.mission h3{margin:0 0 6px;font-size:14.5px}
.force-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.force-card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px}
.force-card h3{margin:0 0 4px;font-size:16px}
.force-card p{color:var(--mut);font-size:12.5px;margin:4px 0 14px}
.vrow{display:flex;align-items:center;gap:10px;padding:7px 0;border-bottom:1px dashed var(--line);font-size:13.5px}
.vrow img{width:86px;border-radius:8px}
.vrow .t{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vrow b{color:var(--mint)}
@media(max-width:800px){.side{display:none}body{display:block}}
</style></head><body>
<div class="side">
<div class="logo"><span class="mk">M</span> MoneyPrint <small>studio</small></div>
<button class="create" onclick="tab('force',null)">＋ Force video</button>
<div class="ws">WORKSPACE</div>
<div class="ws-acc" onclick="filterCh('{{ acc1_name }}')"><span class="av">{{ acc1_name[0] }}</span>{{ acc1_name }}<span class="dot {{ 'ok' if acc1_ok else 'bad' }}"></span></div>
<div class="ws-acc" onclick="filterCh('{{ acc2_name }}')"><span class="av">{{ acc2_name[0] }}</span>{{ acc2_name }}<span class="dot {{ 'ok' if acc2_ok else 'bad' }}"></span></div>
<div class="ws">MENU</div>
<button class="navbtn on" onclick="tab('videos',this)"><span class="ic">▦</span>Videos</button>
<button class="navbtn" onclick="tab('force',this)"><span class="ic">▶</span>Force Make</button>
<button class="navbtn" onclick="tab('missions',this)"><span class="ic">☑</span>Missions</button>
<button class="navbtn" onclick="tab('growth',this)"><span class="ic">↗</span>Growth</button>
<button class="navbtn" onclick="tab('plan',this)"><span class="ic">◷</span>Plan</button>
<button class="navbtn" onclick="tab('accounts',this)"><span class="ic">◉</span>Accounts</button>
<div class="user"><span class="av">{{ acc1_email[0] if acc1_email else "?" }}</span><span>{{ acc1_email }}<small>local · free tier</small></span></div>
</div>
<div class="main">
<div class="sub">{{ src }} &middot; synced {{ synced }} &middot; quota {{ uploads_today }}/{{ max_uploads }}</div>
{% if kill %}<div class="kill-banner">KILL SWITCH ACTIVE (local only)</div>{% endif %}
<div id="liveBox"></div>

<div class="panel on" id="p-videos">
<div class="hero">
<div class="row"><h1>Autopilot</h1><span class="pill {{ 'ok' if wf_on>0 else '' }}">{{ wf_on }}/3 workflows active</span></div>
<p>Set once. MoneyPrint creates your next videos.</p>
<div class="bigstat">{{ acc1_name }} + {{ acc2_name }}</div>
<p>{{ per_day }} videos per day &middot; English &middot; Automatic publishing</p>
<p class="note">Planned posting time</p>
<div class="bigstat">{{ next_slot }}</div>
<p class="note">Asia/Ho_Chi_Minh &middot; {{ next_note }}</p>
</div>
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
<button class="warn" onclick="go('/cancel')" {% if not has_token %}disabled{% endif %}>Cancel jobs</button>
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
<h2 style="margin-top:0">Force make video</h2>
<div id="forceLock"></div>
<p class="note">1 video/luc. Dang co job chay = tat ca nut KHOA (server + UI).</p>
<div class="force-grid">
<div class="force-card"><h3>Acc 1 – {{ acc1_name }}</h3>
<p>1 Short (~12 phut). Hom nay: {{ amap1.done }}/3.</p>
<button class="primary big force-btn" data-locked="{% if not has_token %}1{% endif %}" onclick="trig('shorts-acc1')" {% if not has_token %}disabled{% endif %}>Force 1 Short</button></div>
<div class="force-card"><h3>Acc 2 – {{ acc2_name }}</h3>
<p>1 Short kenh 2. Hom nay: {{ amap2.done }}/3.</p>
<button class="primary big force-btn" data-locked="{% if not has_token %}1{% endif %}" onclick="trig('shorts-acc2')" {% if not has_token %}disabled{% endif %}>Force 1 Short</button></div>
<div class="force-card"><h3>Long video – Acc 1</h3>
<p>1 video &gt;5 phut (~30-60 phut).</p>
<button class="big force-btn" data-locked="{% if not has_token %}1{% endif %}" onclick="trig('long')" {% if not has_token %}disabled{% endif %}>Force 1 Long</button></div>
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
<div class="mission done">
<h3>Gemini API: {{ m.gemini_calls }}/1000 calls hom nay</h3>
<div class="prog"><div style="width:{{ (100*m.gemini_calls//1000) if m.gemini_calls<1000 else 100 }}%">{{ m.gemini_calls }}/1000</div></div>
</div>
</div>

<div class="panel" id="p-growth">
<h2 style="margin-top:0">Tang truong that (views/video/ngay)</h2>
<div class="toolbar"><button onclick="goViews()">Refresh view stats</button><span class="note">goi videos.list that (~1 unit/50 video), cache 6h</span><span id="msgV" class="note"></span></div>
{% for a in accs %}
{% if a.readonly_ok %}
<div class="mission done">
<h3>{{ a.name }}{% if a.channel_title %} – {{ a.channel_title }}{% endif %} <span class="badge ok">LIVE</span></h3>
<div class="grid">
<div class="card"><b>{{ a.subs }}</b><span>subscribers</span></div>
<div class="card"><b>{{ a.views }}</b><span>total views (kenh)</span></div>
<div class="card"><b>{{ a.videos }}</b><span>videos</span></div>
<div class="card"><b>{{ amap[a.slot].done }}/3</b><span>shorts hom nay</span></div>
</div>
</div>
{% endif %}
{% endfor %}
<h2>Views tung video (moi nhat truoc)</h2>
{% if not view_list %}<p class="note">Chua co snapshot – bam <b>Refresh view stats</b> o tren (ton ~1 unit/50 video).</p>{% endif %}
{% for v in view_list %}
<div class="vrow">{% if v.id %}<a href="https://www.youtube.com/watch?v={{ v.id }}" target="_blank"><img src="https://i.ytimg.com/vi/{{ v.id }}/hqdefault.jpg" loading="lazy"></a>{% endif %}<span class="t">{{ v.title }}</span><b>{{ v.views }} views</b></div>
{% endfor %}
<h2>Tong views theo ngay (tu snapshot)</h2>
{% if not view_bars %}<p class="note">Chua co du lieu – bam <b>Refresh view stats</b>, de vai ngay chart se dai ra.</p>{% endif %}
<div class="bar-row">{% for d in view_bars %}<div class="bar" style="height:{{ d.h }}%" title="{{ d.day }}: {{ d.n }}"><b>{{ d.n }}</b><span>{{ d.day[5:] }}</span></div>{% endfor %}</div>
<h2>Upload 14 ngay qua</h2>
{% if total==0 %}<p class="note">Chua co record – bam <b>Sync logs</b> o tab Videos de keo log GitHub ve.</p>{% endif %}
<div class="bar-row">{% for d in bars %}<div class="bar" style="height:{{ d.h }}%" title="{{ d.day }}: {{ d.n }}"><b>{{ d.n }}</b><span>{{ d.day[5:] }}</span></div>{% endfor %}</div>
<div class="grid"><div class="card"><b>{{ streak }}d</b><span>upload streak</span></div></div>
<h2>Thu nhap</h2>
<div class="mission"><h3>Doanh thu uoc tinh: $0</h3>
<div class="prog"><div class="low" style="width:2%">0%</div></div>
<div class="note">Partner (Shorts): <b>1000 subs</b> + <b>10M Shorts views/90 ngay</b>.<br>
{% for a in accs %}{% if a.readonly_ok %}{{ a.name }}: {{ a.subs }}/1000 subs, {{ a.views }} views.<br>{% endif %}{% endfor %}
Du dieu kien bat trong YouTube Studio &gt; Earn.</div></div>
</div>

<div class="panel" id="p-plan">
<h2 style="margin-top:0">Ke hoach GitHub (gio VN = UTC+7)</h2>
<div class="hero">
<p class="note">VIDEO GAN NHAT BAT DAU SAU</p>
<div class="bigstat" id="nextCount">--:--:--</div>
<p class="note" id="nextJob">dang tinh...</p>
</div>
<table id="cronTbl"><tr><th>Job</th><th>UTC</th><th>Gio VN</th><th>Con lai</th><th>Workflow</th></tr>
{% for c in plan_rows %}<tr {% if c.hhmm %}data-utc="{{ c.hhmm }}"{% endif %} data-job="{{ c.job }}"><td>{{ c.job }}</td><td>{{ c.utc }}</td><td>{{ c.vn }}</td><td class="left">{% if not c.hhmm %}chu ky 5 ngay{% else %}--{% endif %}</td><td>{{ c.wf }}</td></tr>{% endfor %}
</table>
<p class="note">Concurrency <b>moneyprint-video</b>: 1 video/luc.<br>
Ping chinh xac: <b>worker-ping.js</b> (Cloudflare) – xem README.</p>
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
<div class="card"><b>{{ a.views }}</b><span>views</span></div>
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
function tab(n,el){document.querySelectorAll('.navbtn').forEach(function(t){t.classList.remove('on');});if(el){el.classList.add('on');}document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('on');});document.getElementById('p-'+n).classList.add('on');}
function filterCh(name){var s=document.getElementById('fCh');if(s){s.value=name;}filtr();tab('videos',document.querySelector('.navbtn'));}
function filtr(){var s=document.getElementById('fStatus').value,k=document.getElementById('fKind').value,c=document.getElementById('fCh').value,t=document.getElementById('fText').value.toLowerCase();document.querySelectorAll('#tbl tr.row').forEach(function(r){var ok=(!s||r.dataset.status===s)&&(!k||r.dataset.kind===k)&&(!c||r.dataset.ch===c)&&(!t||r.dataset.title.includes(t));r.style.display=ok?'':'none';});}
function tog(id){var e=document.getElementById(id);e.style.display=e.style.display==='table-row'?'none':'table-row';}
function go(u){document.getElementById('msg').textContent='working...';fetch(u).then(function(r){return r.json();}).then(function(j){document.getElementById('msg').textContent=j.msg||JSON.stringify(j);setTimeout(function(){location.reload();},1200);}).catch(function(e){document.getElementById('msg').textContent='error: '+e;});}
function goAcc(){document.getElementById('msgAcc').textContent='checking...';fetch('/accounts?force=1').then(function(r){return r.json();}).then(function(j){setTimeout(function(){location.reload();},800);}).catch(function(e){document.getElementById('msgAcc').textContent='error: '+e;});}
function goViews(){document.getElementById('msgV').textContent='fetching...';fetch('/views?force=1').then(function(r){return r.json();}).then(function(j){document.getElementById('msgV').textContent=j.msg||'';setTimeout(function(){location.reload();},800);}).catch(function(e){document.getElementById('msgV').textContent='error: '+e;});}
function trig(wf){var label=wf==='long'?'Long video':(wf==='shorts-acc2'?'Acc 2':'Acc 1');document.getElementById('msgF').textContent='dang kich chay '+label+'...';fetch('/trigger?wf='+wf).then(function(r){return r.json();}).then(function(k){document.getElementById('msgF').textContent=k.msg||JSON.stringify(k);});}
function pad2(n){return (n<10?'0':'')+n;}
function tickCount(){var now=new Date();var nowU=Date.now();var best=null,bestJob='';document.querySelectorAll('#cronTbl tr[data-utc]').forEach(function(r){if(!r.dataset.utc){return;}var p=r.dataset.utc.split(':');var t=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),now.getUTCDate(),parseInt(p[0],10),parseInt(p[1],10),0));if(t.getTime()<=nowU){t=new Date(t.getTime()+86400000);}var s=Math.floor((t.getTime()-nowU)/1000);var txt=Math.floor(s/3600)+'h '+pad2(Math.floor(s%3600/60))+'m '+pad2(s%60)+'s';var cell=r.querySelector('.left');if(cell){cell.textContent=txt;}if(best===null||t.getTime()<best){best=t.getTime();bestJob=r.dataset.job;}});var nc=document.getElementById('nextCount');if(nc&&best!==null){var s=Math.floor((best-nowU)/1000);nc.textContent=Math.floor(s/3600)+'h '+pad2(Math.floor(s%3600/60))+'m '+pad2(s%60)+'s';document.getElementById('nextJob').textContent=bestJob+' · tu dong dem nguoc moi giay';}}
setInterval(tickCount,1000);tickCount();
function live(){fetch('/live').then(function(r){return r.json();}).then(function(j){var b=document.getElementById('liveBox');var busy=(j.active||[]).length>0;document.querySelectorAll('.force-btn').forEach(function(x){if(busy){x.setAttribute('disabled','');}else if(x.dataset.locked!=='1'){x.removeAttribute('disabled');}});var fl=document.getElementById('forceLock');if(fl){fl.innerHTML=busy?'<div class="kill-banner">DANG TAO VIDEO: '+j.active[0].name+' – '+j.active[0].step+' ('+j.active[0].elapsed+'). Tat ca nut force DANG KHOA.</div>':'';}if(!busy){b.innerHTML='';return;}b.innerHTML=j.active.map(function(a){return '<div class="live-banner">LIVE: '+a.name+' – '+a.step+' ('+a.elapsed+') <a href="'+a.url+'" target="_blank">xem log</a></div>';}).join('');}).catch(function(){});}
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


def _yt_token() -> str | None:
    if _rq is None:
        return None
    cid = config.YOUTUBE_CLIENT_ID
    csec = config.YOUTUBE_CLIENT_SECRET
    rt = config.YOUTUBE_REFRESH_TOKEN
    if not (cid and rt):
        return None
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
            return None
        return t.json()["access_token"]
    except Exception:
        return None


def views_snapshot(force: bool = False) -> dict:
    out = {"ids": {}, "trend": [], "at": "-"}
    if _rq is None:
        return out
    try:
        hist = {}
        if VIEWS_FILE.exists():
            hist = json.loads(VIEWS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        hist = {}
    today = datetime.date.today().isoformat()
    if not force and hist.get(today):
        pass
    else:
        vids = []
        for r in state.load():
            vid = r.get("youtube_id", "")
            if vid and vid not in vids:
                vids.append(vid)
        if vids:
            token = _yt_token()
            if token:
                try:
                    snap = {}
                    for i in range(0, len(vids), 50):
                        chunk = vids[i : i + 50]
                        rr = _rq.get(
                            "https://www.googleapis.com/youtube/v3/videos",
                            params={"id": ",".join(chunk), "part": "statistics,snippet"},
                            headers={"Authorization": f"Bearer {token}"},
                            timeout=30,
                        )
                        if rr.status_code != 200:
                            break
                        for it in rr.json().get("items", []):
                            st = it.get("statistics", {})
                            snap[it["id"]] = {
                                "views": int(st.get("viewCount", 0)),
                                "title": it.get("snippet", {}).get("title", ""),
                            }
                    if snap:
                        hist[today] = snap
                        try:
                            VIEWS_FILE.write_text(json.dumps(hist), encoding="utf-8")
                        except OSError:
                            pass
                except Exception:
                    pass
    days = sorted(hist.keys())[-14:]
    trend = []
    for d in days:
        tot = sum(v.get("views", 0) for v in hist[d].values())
        mx = max([tot] + [t["n"] for t in trend]) if trend else tot
        trend.append({"day": d, "n": tot, "h": 0})
    mx = max([t["n"] for t in trend]) if trend else 0
    for t in trend:
        t["h"] = int(100 * t["n"] / mx) if mx else 3
    latest = hist[days[-1]] if days else {}
    id_title = {r.get("youtube_id"): r.get("title", "") for r in state.load()}
    view_list = sorted(
        [
            {
                "id": vid,
                "title": v.get("title") or id_title.get(vid, vid),
                "views": v.get("views", 0),
            }
            for vid, v in latest.items()
        ],
        key=lambda x: -x["views"],
    )
    try:
        ats = VIEWS_FILE.stat().st_mtime if VIEWS_FILE.exists() else 0
        at = (
            datetime.datetime.fromtimestamp(ats).strftime("%H:%M %d/%m") if ats else "-"
        )
    except OSError:
        at = "-"
    out = {"trend": trend, "list": view_list, "at": at}
    return out


def _next_slot() -> tuple[str, str]:
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    best = None
    for c in CRONS:
        hhmm = c["utc"].split(" ")[0]
        try:
            hh, mm = int(hhmm[:2]), int(hhmm[3:5])
        except (ValueError, IndexError):
            continue
        cand = now_utc.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if cand <= now_utc:
            cand += datetime.timedelta(days=1)
        if best is None or cand < best[0]:
            best = (cand, c["job"])
    if not best:
        return "-", "-"
    vn = best[0] + datetime.timedelta(hours=7)
    return vn.strftime("%b %d, %H:%M"), f"{best[1]} · cron tu chay"


def _wf_states() -> int:
    res = _gh_api("GET", "/actions/workflows?per_page=10")
    if not res["ok"]:
        return 0
    n = 0
    for w in res["data"].get("workflows", []):
        if w.get("state") == "active" and w.get("path", "").startswith(
            ".github/workflows/"
        ) and w.get("path", "") in (
            ".github/workflows/shorts-acc1.yml",
            ".github/workflows/shorts-acc2.yml",
            ".github/workflows/long.yml",
        ):
            n += 1
    return n


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
    gu = state.gemini_usage()
    return {
        "gemini_calls": gu.get("count", 0),
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
    token = _yt_token()
    if not token:
        return out
    try:
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
    views = views_snapshot()
    nxt, nxt_note = _next_slot()
    plan_rows = []
    for c in CRONS:
        m = c["utc"]
        if "/5" in c["job"]:
            plan_rows.append(
                {"job": c["job"], "utc": m + " UTC", "vn": "22:00 VN /5d", "wf": c["wf"], "hhmm": ""}
            )
        else:
            hh = (int(m[:2]) + 7) % 24
            plan_rows.append(
                {
                    "job": c["job"],
                    "utc": m + " UTC",
                    "vn": f"{hh:02d}:{m[3:5]} VN",
                    "wf": c["wf"],
                    "hhmm": m,
                }
            )
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
        acc1_ok=bool(acc1.get("readonly_ok")),
        acc2_ok=bool(acc2.get("readonly_ok")),
        amap1=amap.get("1", {"done": 0}),
        amap2=amap.get("2", {"done": 0}),
        ch=channel_stats(),
        view_list=views["list"],
        view_bars=views["trend"],
        wf_on=_wf_states(),
        per_day=6,
        plan_rows=plan_rows,
        next_slot=nxt,
        next_note=nxt_note,
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


@app.route("/views")
def views():
    force = request.args.get("force") == "1"
    snap = views_snapshot(force=force)
    return jsonify(
        {"ok": True, "msg": f"{len(snap['list'])} videos tracked", "at": snap["at"]}
    )


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
    busy = _gh_api("GET", "/actions/runs?per_page=5")
    if busy["ok"]:
        for r in busy["data"].get("workflow_runs", []):
            if r.get("status") in ("queued", "in_progress"):
                return jsonify(
                    {
                        "ok": False,
                        "msg": f"KHOA: dang co job '{r['name']}' chay. Doi xong moi force.",
                    }
                )
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
