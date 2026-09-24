import http.server
import re
import secrets
import sys
import urllib.parse
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
REDIRECT_PORT = 8765
REDIRECT = f"http://127.0.0.1:{REDIRECT_PORT}"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload"
    " https://www.googleapis.com/auth/youtube.readonly"
)

CID_RE = re.compile(r"^\d+-[a-z0-9\-]+\.apps\.googleusercontent\.com$", re.I)
CSEC_RE = re.compile(r"^[A-Za-z0-9_\-]{10,}$")


def valid_client_id(v: str) -> bool:
    return bool(CID_RE.match(v.strip().strip('"').strip("'")))


def valid_client_secret(v: str) -> bool:
    v = v.strip().strip('"').strip("'")
    return bool(CSEC_RE.match(v)) and ("GOCSPX-" in v or len(v) >= 20)


def ask(prompt: str, check, hint: str) -> str:
    while True:
        v = input(prompt).strip().strip('"').strip("'")
        if check(v):
            return v
        print(f"sai format. {hint}")


def read_env(path: Path = ENV) -> dict:
    data = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def write_env(values: dict, path: Path = ENV) -> None:
    data = read_env(path)
    data.update(values)
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class Handler(http.server.BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in q:
            Handler.code = q["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("OK - dong tab nay, quay lai terminal.".encode())
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args):
        pass


def fetch_refresh_token(client_id: str, client_secret: str) -> str:
    import requests

    state = secrets.token_urlsafe(16)
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    print("\nMo browser de dang nhap Google...")
    print(url + "\n")
    webbrowser.open(url)
    server = http.server.HTTPServer(("127.0.0.1", REDIRECT_PORT), Handler)
    while Handler.code is None:
        server.handle_request()
    server.server_close()
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": Handler.code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"exchange failed: {r.status_code} {r.text[:300]}")
    rt = r.json().get("refresh_token", "")
    if not rt:
        raise SystemExit("Google khong tra refresh_token. Vao myaccount.google.com > Security > Third-party access, go quyen app, roi chay lai.")
    return rt


def main() -> None:
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Buoc 1: GCP > API et services > Identifiants > bam vao client Desktop")
        print("Buoc 2: copy 2 chuoi ID client + Code secret du client, paste vao day")
        print("Buoc 3: script tu mo browser lay refresh token, tu ghi .env")
        return
    print("=" * 60)
    print("YouTube auth wizard - chi can copy/paste 2 chuoi tu Google Cloud")
    print("Vao: GCP > API et services > Identifiants > bam vao client Desktop")
    print("=" * 60)
    cid = ask(
        "\n1) Paste ID client (dang ...apps.googleusercontent.com): ",
        valid_client_id,
        "Vi du: 123456789012-abcxyz.apps.googleusercontent.com",
    )
    csec = ask(
        "2) Paste Code secret du client (bat dau GOCSPX-): ",
        valid_client_secret,
        "Vi du: GOCSPX-AbCdEfGhIjKlMnOpQrSt",
    )
    write_env({"YOUTUBE_CLIENT_ID": cid, "YOUTUBE_CLIENT_SECRET": csec})
    print("\nDa ghi ID + Secret vao .env. Gio lay refresh token...")
    rt = fetch_refresh_token(cid, csec)
    write_env({"YOUTUBE_REFRESH_TOKEN": rt})
    print("\n" + "=" * 60)
    print("XONG. Da luu ca 3 gia tri vao .env")
    print("Copy 3 gia tri nay vao GitHub Secrets (Repo > Settings > Secrets > Actions):")
    print("  YOUTUBE_CLIENT_ID")
    print("  YOUTUBE_CLIENT_SECRET")
    print("  YOUTUBE_REFRESH_TOKEN")
    print("=" * 60)


if __name__ == "__main__":
    main()
