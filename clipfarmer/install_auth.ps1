$dest = "C:\clipfarmer\clipfarmer\tiktok_auth.py"

$code = @'
import os
import sys
import json
import base64
import hashlib
import secrets
import requests
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

CLIENT_KEY    = os.environ.get("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET")
REDIRECT_URI  = "http://localhost:3000/callback"
SCOPES        = "video.upload,video.publish"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"

if not CLIENT_KEY:
    print("[FATAL] TIKTOK_CLIENT_KEY is not set.")
    sys.exit(1)

if not CLIENT_SECRET:
    print("[FATAL] TIKTOK_CLIENT_SECRET is not set.")
    sys.exit(1)

def generate_code_verifier():
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()

def generate_code_challenge(verifier):
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

class AuthState:
    code  = None
    state = None
    done  = False

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code  = params.get("code",  [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]
        if error:
            self._respond(f"<h2>Error: {error}</h2>")
            AuthState.done = True
            return
        if not code:
            self._respond("<h2>No code received.</h2>")
            return
        if state != AuthState.state:
            self._respond("<h2>State mismatch. Aborting.</h2>")
            AuthState.done = True
            return
        AuthState.code = code
        AuthState.done = True
        self._respond("<h2 style='font-family:sans-serif;color:green;'>Authorized! Return to your terminal.</h2>")

    def _respond(self, body):
        html = f"<html><body>{body}</body></html>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, format, *args):
        pass

def build_auth_url(state, code_challenge):
    params = {
        "client_key":            CLIENT_KEY,
        "response_type":         "code",
        "scope":                 SCOPES,
        "redirect_uri":          REDIRECT_URI,
        "state":                 state,
        "code_challenge":        code_challenge,
        "code_challenge_method": "S256",
    }
    return "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)

def exchange_code_for_token(code, code_verifier):
    payload = {
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(TOKEN_URL, data=payload, headers=headers, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} - {response.text}")
    body = response.json()
    if "data" not in body:
        raise RuntimeError(f"Unexpected response: {body}")
    return body["data"]

def main():
    code_verifier   = generate_code_verifier()
    code_challenge  = generate_code_challenge(code_verifier)
    AuthState.state = secrets.token_urlsafe(16)

    server = HTTPServer(("localhost", 3000), CallbackHandler)
    Thread(target=server.serve_forever, daemon=True).start()

    auth_url = build_auth_url(AuthState.state, code_challenge)

    print("\n" + "=" * 60)
    print("Opening browser for TikTok login with @kenis_ter ...")
    print("If browser does not open, copy this URL manually:")
    print("=" * 60)
    print(f"\n{auth_url}\n")
    print("=" * 60)
    print("Waiting for redirect to localhost:3000 ...")
    print("=" * 60)

    webbrowser.open(auth_url)

    while not AuthState.done:
        pass

    server.shutdown()

    if not AuthState.code:
        print("\n[FATAL] No code received.")
        sys.exit(1)

    print("\n[OK] Code received. Getting access token ...")

    try:
        token_data = exchange_code_for_token(AuthState.code, code_verifier)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)

    access_token  = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in    = token_data.get("expires_in")
    open_id       = token_data.get("open_id")

    print("\n" + "=" * 60)
    print("SUCCESS - YOUR ACCESS TOKEN")
    print("=" * 60)
    print(f"\nAccess Token  : {access_token}")
    print(f"Refresh Token : {refresh_token}")
    print(f"Expires In    : {expires_in} seconds")
    print(f"Open ID       : {open_id}")
    print("\n" + "=" * 60)
    print("Paste this into C:\\clipfarmer\\config.json:")
    print("=" * 60)
    print(json.dumps({
        "access_token":  access_token,
        "open_id":       open_id,
        "video_path":    "C:\\clipfarmer\\storage\\review_demo.mp4",
        "channel_id":    "ch_01"
    }, indent=2))
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
'@

Set-Content -Path $dest -Value $code -Encoding UTF8
Write-Host "Done. tiktok_auth.py written to $dest"