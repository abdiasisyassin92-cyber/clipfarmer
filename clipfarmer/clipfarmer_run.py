import sys
import json
import os
import time
import secrets
import requests
import urllib.parse
import webbrowser
from datetime import datetime

# ── CREDENTIALS ──────────────────────────────
CLIENT_KEY    = "sbawbjts47a736sm3k"
CLIENT_SECRET = "xFc51Pbzc5DxZ7ymbBm0qtplOcy9ev4m"
REDIRECT_URI  = "https://abdiasisyassin92-cyber.github.io/clipfarmer-site/"
TOKEN_URL     = "https://open.tiktokapis.com/v2/oauth/token/"
UPLOAD_INIT   = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
VIDEO_PATH    = r"C:\clipfarmer\storage\review_demo.mp4"

def log(level, msg):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [{level}] {msg}", flush=True)

# ── STEP 1: GET TOKEN ─────────────────────────
state = secrets.token_urlsafe(16)
params = {
    "client_key":    CLIENT_KEY,
    "response_type": "code",
    "scope":         "user.info.basic,video.upload",
    "redirect_uri":  REDIRECT_URI,
    "state":         state,
}
auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)

print("\nOpening TikTok login in browser...")
print(f"\nURL: {auth_url}\n")
webbrowser.open(auth_url)

print("After you approve, TikTok redirects to your GitHub site.")
print("The browser address bar will show a long URL starting with:")
print("https://abdiasisyassin92-cyber.github.io/clipfarmer-site/?code=...\n")
callback = input("Paste that full URL here: ").strip()

parsed = urllib.parse.parse_qs(urllib.parse.urlparse(callback).query)
code = parsed.get("code", [None])[0]

if not code:
    print("\n[ERROR] No code found. Make sure you copied the URL AFTER approving.")
    sys.exit(1)

log("INFO", "Code received. Getting access token...")

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

token_resp = r.json()
if "access_token" in token_resp:
    access_token = token_resp["access_token"]
elif "data" in token_resp:
    access_token = token_resp["data"]["access_token"]
else:
    print(f"[ERROR] Token exchange failed: {token_resp}")
    sys.exit(1)
log("INFO", f"Token received: {access_token[:30]}...")

# ── STEP 2: UPLOAD INIT ───────────────────────
if not os.path.exists(VIDEO_PATH):
    log("ERROR", f"Video not found: {VIDEO_PATH}")
    sys.exit(1)

file_size = os.path.getsize(VIDEO_PATH)
log("INFO", f"Video: {VIDEO_PATH} | Size: {file_size:,} bytes")

CHUNK_SIZE = 64 * 1024 * 1024  # 64 MB — TikTok max per chunk

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type":  "application/json; charset=UTF-8",
}

total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE  # ceil division
chunk_size   = min(CHUNK_SIZE, file_size)

# Inbox endpoint only accepts source_info (no post_info)
payload = {
    "source_info": {
        "source":            "FILE_UPLOAD",
        "video_size":        file_size,
        "chunk_size":        chunk_size,
        "total_chunk_count": total_chunks,
    },
}

log("INFO", f"Chunks: {total_chunks} x up to {chunk_size:,} bytes")
log("INFO", "Initializing inbox upload...")
init_r = requests.post(UPLOAD_INIT, headers=headers, json=payload, timeout=30)

if init_r.status_code != 200:
    log("ERROR", f"Init failed: HTTP {init_r.status_code} - {init_r.text}")
    sys.exit(1)

init_body  = init_r.json()
error_code = init_body.get("error", {}).get("code", "ok")
if error_code != "ok":
    log("ERROR", f"Init API error: {error_code} - {init_body}")
    sys.exit(1)

upload_url = init_body["data"]["upload_url"]
publish_id = init_body["data"]["publish_id"]
log("INFO", f"publish_id: {publish_id}")

# ── STEP 3: CHUNKED UPLOAD ────────────────────
log("INFO", f"Uploading {file_size:,} bytes in {total_chunks} chunk(s)...")

with open(VIDEO_PATH, "rb") as f:
    for chunk_idx in range(total_chunks):
        start = chunk_idx * CHUNK_SIZE
        data  = f.read(CHUNK_SIZE)
        end   = start + len(data) - 1

        upload_headers = {
            "Content-Type":   "video/mp4",
            "Content-Length": str(len(data)),
            "Content-Range":  f"bytes {start}-{end}/{file_size}",
        }

        log("INFO", f"  Sending chunk {chunk_idx + 1}/{total_chunks} "
                    f"(bytes {start}-{end})...")
        upload_r = requests.put(
            upload_url, headers=upload_headers, data=data, timeout=300
        )

        if upload_r.status_code not in (200, 201, 204, 206):
            log("ERROR", f"Chunk {chunk_idx + 1} failed: "
                        f"HTTP {upload_r.status_code} - {upload_r.text[:300]}")
            sys.exit(1)

        log("INFO", f"  Chunk {chunk_idx + 1} OK — HTTP {upload_r.status_code}")

log("INFO", "All chunks uploaded successfully.")
log("INFO", f"publish_id '{publish_id}' is processing — check TikTok inbox.")
print("\n" + "=" * 60)
print("PIPELINE COMPLETE")
print(f"publish_id : {publish_id}")
print(f"Check      : TikTok app → Inbox → Drafts")
print("=" * 60)
