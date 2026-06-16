import sys
import json
import secrets
import requests
import urllib.parse
import webbrowser

CLIENT_KEY    = "sbawbjts47a736sm3k"
CLIENT_SECRET = "xFc51Pbzc5DxZ7ymbBm0qtplOcy9ev4m"
REDIRECT_URI  = "https://abdiasisyassin92-cyber.github.io/clipfarmer-site/"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"
CONFIG_PATH   = r"C:\clipfarmer\clipfarmer\config.json"

state = secrets.token_urlsafe(16)

params = {
    "client_key":    CLIENT_KEY,
    "response_type": "code",
    "scope":         "user.info.basic,video.upload",
    "redirect_uri":  REDIRECT_URI,
    "state":         state,
}

url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)

print("\nOpening browser...")
webbrowser.open(url)

print("\nAfter approving, copy the FULL URL from your browser and paste below.\n")
callback = input("Paste full redirect URL here: ").strip()

parsed = urllib.parse.parse_qs(urllib.parse.urlparse(callback).query)
code = parsed.get("code", [None])[0]

if not code:
    print("[ERROR] No code found.")
    sys.exit(1)

print("\nExchanging code for token...")

r = requests.post(
    TOKEN_URL,
    data={
        "client_key":    CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
        "redirect_uri":  REDIRECT_URI,
    },
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    timeout=30,
)

data = r.json()

if "data" not in data:
    print(f"[ERROR] {data}")
    sys.exit(1)

token_data    = data["data"]
access_token  = token_data.get("access_token")
refresh_token = token_data.get("refresh_token")
open_id       = token_data.get("open_id")

print(f"\nAccess Token: {access_token}")

# Write directly into config.json
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

config["tiktok"]["access_token"]  = access_token
config["tiktok"]["refresh_token"] = refresh_token
config["tiktok"]["open_id"]       = open_id

with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)

print(f"\n[OK] Token saved to {CONFIG_PATH}")
print("\nRunning uploader now...")

import subprocess
subprocess.run([sys.executable, r"C:\clipfarmer\clipfarmer\tiktok_uploader.py"])