"""
debug_meta_handshake.py — ClipFarmer Meta API Diagnostic Tool
Inspects any Meta access token and diagnoses Instagram permission issues.

Usage:
  python debug_meta_handshake.py --token YOUR_TOKEN_HERE
  python debug_meta_handshake.py  (reads from config.json or IG_ACCESS_TOKEN env var)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
CONFIG_FILE    = Path("C:/clipfarmer/config.json")

REQUIRED_SCOPES = [
    "instagram_business_basic",
    "instagram_business_content_publish",
    "instagram_business_manage_messages",
    "pages_show_list",
    "pages_read_engagement",
]

CRITICAL_SCOPES = [
    "instagram_business_basic",
    "instagram_business_content_publish",
]


def log(message: str, level: str = "INFO"):
    tag = {
        "INFO":  "[ INFO ]",
        "OK":    "[  OK  ]",
        "WARN":  "[ WARN ]",
        "ERR":   "[ FAIL ]",
        "HEAD":  "[======]",
        "STEP":  "[ STEP ]",
        "FIX":   "[ FIX  ]",
    }.get(level, "[ INFO ]")
    print(f"{tag} {message}", flush=True)


def get_token(override: str = "") -> str:
    if override:
        return override
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    if not token:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            token = cfg.get("instagram", {}).get("access_token", "")
        except Exception:
            pass
    return token


def safe_get(url: str, params: dict) -> dict:
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json()
        return {"_error": f"HTTP {r.status_code}", "_body": r.text[:400]}
    except Exception as e:
        return {"_error": str(e)}


# ── Step 1: Debug token introspection ────────────────────────────────────────

def inspect_token(token: str) -> dict:
    log("=" * 60, "HEAD")
    log("Step 1 -- Token Introspection via /debug_token", "STEP")
    log("=" * 60, "HEAD")

    # For /debug_token we use the token as both input and access token
    # (works for User tokens without an App token)
    url    = f"{GRAPH_API_BASE}/debug_token"
    params = {
        "input_token":  token,
        "access_token": token,
    }

    data = safe_get(url, params)

    if "_error" in data:
        log(f"Could not reach /debug_token: {data['_error']}", "ERR")
        log("Falling back to /me/permissions endpoint.", "INFO")
        return {}

    info = data.get("data", {})

    if not info:
        log("Meta returned empty debug data. Token may be malformed.", "ERR")
        return {}

    # Token type
    token_type = info.get("type", "UNKNOWN")
    app_id     = info.get("app_id", "N/A")
    app_name   = info.get("application", "N/A")
    is_valid   = info.get("is_valid", False)
    expires_at = info.get("expires_at", 0)
    user_id    = info.get("user_id", "N/A")

    log(f"Token type         : {token_type}", "INFO")
    log(f"Valid              : {is_valid}", "OK" if is_valid else "ERR")
    log(f"App ID             : {app_id}", "INFO")
    log(f"App name           : {app_name}", "INFO")
    log(f"User ID            : {user_id}", "INFO")

    if expires_at:
        exp_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
        log(f"Expires            : {exp_dt.strftime('%Y-%m-%d %H:%M UTC')}", "INFO")
    else:
        log("Expires            : Never (Long-Lived or System User token)", "OK")

    if not is_valid:
        log("TOKEN IS INVALID. Generate a new token in Graph API Explorer.", "ERR")
        _print_token_fix()
        return info

    # Token type diagnosis
    log("", "INFO")
    if token_type == "USER":
        log("Token type is USER -- correct for Instagram publishing.", "OK")
    elif token_type == "PAGE":
        log("Token type is PAGE -- this will NOT work for Instagram publishing.", "WARN")
        log("Instagram requires a USER token, not a Page token.", "WARN")
        _print_token_type_fix()
    else:
        log(f"Token type is {token_type} -- verify this is correct for your use case.", "WARN")

    return info


# ── Step 2: Permissions check ─────────────────────────────────────────────────

def check_permissions(token: str) -> set:
    log("", "INFO")
    log("=" * 60, "HEAD")
    log("Step 2 -- Active Scope Matrix via /me/permissions", "STEP")
    log("=" * 60, "HEAD")

    url    = f"{GRAPH_API_BASE}/me/permissions"
    params = {"access_token": token}

    data = safe_get(url, params)

    if "_error" in data:
        log(f"Could not reach /me/permissions: {data['_error']}", "ERR")
        return set()

    permissions = data.get("data", [])

    if not permissions:
        log("No permissions returned. Token may lack basic access.", "ERR")
        return set()

    granted = set()
    declined = set()

    log(f"{'Permission':<50} {'Status'}", "INFO")
    log("-" * 65, "INFO")

    for p in sorted(permissions, key=lambda x: x.get("permission", "")):
        name   = p.get("permission", "unknown")
        status = p.get("status", "unknown")
        if status == "granted":
            granted.add(name)
            marker = "OK"
        else:
            declined.add(name)
            marker = "WARN"
        log(f"  {name:<48} {status.upper()}", marker)

    log("", "INFO")
    log(f"Total granted : {len(granted)}", "INFO")
    log(f"Total declined: {len(declined)}", "INFO")

    return granted


# ── Step 3: Critical scope diagnosis ──────────────────────────────────────────

def diagnose_scopes(granted: set):
    log("", "INFO")
    log("=" * 60, "HEAD")
    log("Step 3 -- Critical Scope Diagnosis", "STEP")
    log("=" * 60, "HEAD")

    missing = []
    for scope in CRITICAL_SCOPES:
        if scope in granted:
            log(f"  {scope} -- PRESENT", "OK")
        else:
            log(f"  {scope} -- MISSING", "ERR")
            missing.append(scope)

    if not missing:
        log("", "INFO")
        log("All critical scopes are present. Token is ready for Instagram publishing.", "OK")
        return

    log("", "INFO")
    log("MISSING CRITICAL SCOPES DETECTED", "ERR")
    log("Follow the steps below to fix the permission hierarchy.", "INFO")
    log("", "INFO")
    _print_scope_fix(missing)


# ── Fix instructions ──────────────────────────────────────────────────────────

def _print_token_fix():
    log("", "INFO")
    log("=" * 60, "HEAD")
    log("HOW TO GENERATE A VALID TOKEN", "FIX")
    log("=" * 60, "HEAD")
    log("1. Go to: https://developers.facebook.com/tools/explorer/", "FIX")
    log("2. Select your App from the top-right dropdown.", "FIX")
    log("3. Click 'Generate Access Token'.", "FIX")
    log("4. In the permissions panel, check:", "FIX")
    log("     - instagram_business_basic", "FIX")
    log("     - instagram_business_content_publish", "FIX")
    log("     - pages_show_list", "FIX")
    log("     - pages_read_engagement", "FIX")
    log("5. Click 'Generate Access Token' and approve the dialog.", "FIX")
    log("6. Copy the token and paste it into config.json.", "FIX")
    log("7. Exchange for a Long-Lived token:", "FIX")
    log("   GET /oauth/access_token", "FIX")
    log("     ?grant_type=fb_exchange_token", "FIX")
    log("     &client_id=YOUR_APP_ID", "FIX")
    log("     &client_secret=YOUR_APP_SECRET", "FIX")
    log("     &fb_exchange_token=YOUR_SHORT_LIVED_TOKEN", "FIX")


def _print_token_type_fix():
    log("", "INFO")
    log("=" * 60, "HEAD")
    log("HOW TO GET A USER TOKEN INSTEAD OF A PAGE TOKEN", "FIX")
    log("=" * 60, "HEAD")
    log("1. Go to: https://developers.facebook.com/tools/explorer/", "FIX")
    log("2. In the top-right, make sure 'User Token' is selected,", "FIX")
    log("   NOT 'Page Access Token'.", "FIX")
    log("3. Re-generate the token with the required permissions.", "FIX")
    log("4. The /debug_token type field should show USER, not PAGE.", "FIX")


def _print_scope_fix(missing: list):
    log("=" * 60, "HEAD")
    log("HOW TO RE-STITCH THE INSTAGRAM PERMISSION HIERARCHY", "FIX")
    log("=" * 60, "HEAD")
    log("", "INFO")
    log("The 'Object does not exist' error usually means one of:", "INFO")
    log("  A) Your Instagram account is not linked to a Facebook Page.", "INFO")
    log("  B) Your token does not have the required scopes.", "INFO")
    log("  C) Your Instagram account is Personal, not Business/Creator.", "INFO")
    log("", "INFO")

    log("STEP A -- Confirm Instagram is a Business or Creator account:", "FIX")
    log("  1. Open Instagram app -> Settings -> Account.", "FIX")
    log("  2. Tap 'Switch to Professional Account'.", "FIX")
    log("  3. Choose 'Business' or 'Creator'.", "FIX")
    log("", "INFO")

    log("STEP B -- Link Instagram to your Facebook Page:", "FIX")
    log("  1. Go to https://business.facebook.com/settings", "FIX")
    log("  2. Select your Business -> Instagram Accounts.", "FIX")
    log("  3. Click 'Add' and connect @kenis_ter to 'Kenis Ter Media' Page.", "FIX")
    log("", "INFO")

    log("STEP C -- Re-generate token with correct scopes:", "FIX")
    log("  1. Go to https://developers.facebook.com/tools/explorer/", "FIX")
    log("  2. Select your App.", "FIX")
    log("  3. Select 'User Token' (not Page Token).", "FIX")
    log("  4. Enable these permissions:", "FIX")
    for scope in missing:
        log(f"       + {scope}", "FIX")
    log("       + pages_show_list", "FIX")
    log("       + pages_read_engagement", "FIX")
    log("  5. Click Generate Access Token and approve.", "FIX")
    log("  6. Run this diagnostic again to confirm scopes are active.", "FIX")
    log("", "INFO")

    log("STEP D -- Get your Instagram Business Account ID:", "FIX")
    log("  After generating a valid User token, run:", "FIX")
    log("  GET /me/accounts?access_token=YOUR_TOKEN", "FIX")
    log("  Then for each page ID returned, run:", "FIX")
    log("  GET /{PAGE_ID}?fields=instagram_business_account&access_token=YOUR_TOKEN", "FIX")
    log("  The instagram_business_account.id value is your account_id for config.json.", "FIX")
    log("=" * 60, "HEAD")


# ── Step 4: Fetch linked Instagram account ID ─────────────────────────────────

def fetch_instagram_account_id(token: str):
    log("", "INFO")
    log("=" * 60, "HEAD")
    log("Step 4 -- Locate Linked Instagram Business Account ID", "STEP")
    log("=" * 60, "HEAD")

    pages_data = safe_get(
        f"{GRAPH_API_BASE}/me/accounts",
        {"access_token": token, "fields": "id,name,instagram_business_account"}
    )

    if "_error" in pages_data or not pages_data.get("data"):
        log("Could not retrieve Facebook Pages. Check pages_show_list permission.", "WARN")
        return

    pages = pages_data.get("data", [])
    log(f"Found {len(pages)} Facebook Page(s) linked to this token:", "INFO")

    found_ig = False
    for page in pages:
        page_id   = page.get("id", "N/A")
        page_name = page.get("name", "Unknown")
        ig        = page.get("instagram_business_account")

        log(f"", "INFO")
        log(f"  Page name : {page_name}", "INFO")
        log(f"  Page ID   : {page_id}", "INFO")

        if ig:
            ig_id = ig.get("id", "N/A")
            log(f"  Instagram Business Account ID : {ig_id}", "OK")
            log(f"  --> Add this to config.json as instagram.account_id", "FIX")
            found_ig = True
        else:
            log(f"  No Instagram Business Account linked to this Page.", "WARN")

    if not found_ig:
        log("", "INFO")
        log("No Instagram Business Account found on any linked Page.", "ERR")
        log("Complete Step B above to link @kenis_ter to your Facebook Page.", "FIX")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ClipFarmer -- Meta API Handshake Diagnostic"
    )
    parser.add_argument("--token", default="", help="Access token to inspect")
    args = parser.parse_args()

    print("")
    log("ClipFarmer -- Meta API Handshake Diagnostic", "HEAD")
    log("@kenisterjz / @kenis_ter Instagram Integration", "INFO")
    print("")

    token = get_token(override=args.token)

    if not token:
        log("No token found. Provide one with --token or set IG_ACCESS_TOKEN.", "ERR")
        log("Or add it to C:\\clipfarmer\\config.json under instagram.access_token", "INFO")
        sys.exit(1)

    log(f"Token loaded. First 20 chars: {token[:20]}...", "INFO")
    print("")

    token_info = inspect_token(token)
    granted    = check_permissions(token)

    if granted:
        diagnose_scopes(granted)
        fetch_instagram_account_id(token)
    else:
        log("Could not retrieve permissions. Run token fix steps above.", "ERR")
        _print_token_fix()

    print("")
    log("Diagnostic complete. Review output above for action items.", "INFO")
    print("")
