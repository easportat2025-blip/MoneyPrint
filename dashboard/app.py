import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask, jsonify, render_template_string

import config
import state

app = Flask(__name__)

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>ReZain – MoneyPrint</title>
<style>
body{font-family:ui-monospace,monospace;background:#0b1020;color:#e6edf3;margin:0;padding:24px}
h1{color:#7ee787;font-size:18px}
.meta{color:#8b949e;margin-bottom:16px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #30363d;padding:8px;text-align:left;vertical-align:top}
th{background:#161b22;color:#7ee787}
tr:nth-child(even){background:#11161d}
.st-done{color:#3fb950}.st-failed{color:#f85149}.st-uploaded{color:#58a6ff}
.st-uploading,.st-rendering,.st-researching{color:#d29922}
a{color:#58a6ff}
.kill{background:#3d1214;border:1px solid #f85149;padding:8px 12px;border-radius:6px;display:inline-block;margin-bottom:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;background:#21262d;border:1px solid #30363d}
</style></head><body>
<h1>ReZain · MoneyPrint dashboard</h1>
<div class="meta">state: {{ source }} · records: {{ records|length }} · uploads today: {{ uploads_today }}/{{ max_uploads }}</div>
{% if kill %}<div class="kill">KILL SWITCH ACTIVE</div>{% endif %}
<table>
<tr><th>ID</th><th>Kind</th><th>Status</th><th>Title</th><th>YouTube</th><th>Stages</th><th>Error</th><th>Updated</th></tr>
{% for r in records %}
<tr>
<td>{{ r.id }}</td>
<td>{{ r.kind }}</td>
<td class="st-{{ r.status }}">{{ r.status }}</td>
<td>{{ r.title }}</td>
<td>{% if r.youtube_url %}<a href="{{ r.youtube_url }}" target="_blank">open</a>{% else %}—{% endif %}</td>
<td>
{% for name, s in (r.stages or {}).items() %}
<span class="badge" title="{{ s.detail }}">{{ "✓" if s.ok else "✗" }} {{ name }}</span>
{% endfor %}
</td>
<td style="color:#f85149;max-width:280px">{{ r.error }}</td>
<td>{{ r.updated_at[:19] }}</td>
</tr>
{% endfor %}
</table>
<p class="meta">refresh: <a href="/">/</a> · API: <a href="/api">/api</a></p>
</body></html>"""


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
    return [], "empty (run pipeline or pull logs branch)"


@app.route("/")
def index():
    records, source = _source_state()
    return render_template_string(
        PAGE,
        records=records,
        source=source,
        uploads_today=state.uploads_today(),
        max_uploads=config.MAX_DAILY_UPLOADS,
        kill=config.kill_requested(),
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


@app.route("/kill")
def kill():
    if config.KILL_FILE.exists():
        config.KILL_FILE.unlink()
        return jsonify(kill=False)
    config.KILL_FILE.write_text("1", encoding="utf-8")
    return jsonify(kill=True)


def main():
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
