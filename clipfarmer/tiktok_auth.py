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
print("\nURL:", url)
webbrowser.open(url)

print("\nAfter approving on TikTok, copy the FULL URL")
print("from your browser address bar and paste it below.\n")

callback = input("Paste full redirect URL here: ").strip()

parsed = urllib.parse.parse_qs(urllib.parse.urlparse(callback).query)
code = parsed.get("code", [None])[0]

if not code:
    print("[ERROR] No code found in URL.")
    sys.exit(1)

print("\nExchanging code for access token...")

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

print("\nResponse:", r.status_code)
data = r.json()
print(json.dumps(data, indent=2))

if "data" in data:
    token = data["data"].get("access_token")
    print("\n" + "=" * 60)
    print("ACCESS TOKEN:", token)
    print("=" * 60)
