import http.server
import json
import secrets
import urllib.parse
import webbrowser
from pathlib import Path

CLIENT_ID = ""
CLIENT_SECRET = ""
REDIRECT_PORT = 8765
REDIRECT = f"http://127.0.0.1:{REDIRECT_PORT}"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload"
    " https://www.googleapis.com/auth/youtube.readonly"
)
ROOT = Path(__file__).resolve().parents[1]


def _load_env():
    global CLIENT_ID, CLIENT_SECRET
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "YOUTUBE_CLIENT_ID":
                CLIENT_ID = v.strip()
            if k.strip() == "YOUTUBE_CLIENT_SECRET":
                CLIENT_SECRET = v.strip()


class Handler(http.server.BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in q:
            Handler.code = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK - close this tab and return to terminal.")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args):
        pass


def main():
    _load_env()
    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit(
            "Fill YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first."
        )
    state = secrets.token_urlsafe(16)
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        + urllib.parse.urlencode(
            {
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT,
                "response_type": "code",
                "scope": SCOPES,
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
    )
    print("Opening browser for Google consent...")
    print(url)
    webbrowser.open(url)

    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    while Handler.code is None:
        server.handle_request()
    server.server_close()

    import requests

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": Handler.code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"exchange failed: {r.status_code} {r.text}")
    data = r.json()
    rt = data.get("refresh_token", "")
    if not rt:
        raise SystemExit("no refresh_token returned (revoke app access and retry)")
    print("\nREFRESH TOKEN:\n" + rt + "\n")
    print("Put it in .env as YOUTUBE_REFRESH_TOKEN=... and GitHub Secrets.")


if __name__ == "__main__":
    main()
