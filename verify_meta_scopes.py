"""
verify_meta_scopes.py — ClipFarmer Meta API Permission Validator
Checks that the configured access token has the required Instagram permissions.

Usage:
  python verify_meta_scopes.py
  python verify_meta_scopes.py --token YOUR_TOKEN_HERE
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
CONFIG_FILE    = Path("C:/clipfarmer/config.json")
ERROR_LOG      = Path("C:/clipfarmer/logs/meta_errors.log")
ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

REQUIRED_SCOPES = [
    "instagram_business_basic",
    "instagram_business_content_publish",
]


def log(message: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    tag = {"INFO": "[INFO]", "OK": "[ OK ]", "WARN": "[WARN]", "ERR": "[ERR ]"}.get(level, "[INFO]")
    print(f"[{ts}] {tag} {message}", flush=True)


def log_error(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass
    log(message, "ERR")


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


def verify_meta_scopes(token: str = "") -> bool:
    """
    Calls /me/permissions and checks for required Instagram scopes.
    Returns True if all required permissions are GRANTED, False otherwise.
    """
    log("=" * 55)
    log("Meta API Permission Verification")
    log("=" * 55)
    log(f"Required scopes: {', '.join(REQUIRED_SCOPES)}")
    log("Contacting Meta Graph API...")

    if not token:
        token = get_token()

    if not token:
        msg = "No access token found. Set IG_ACCESS_TOKEN or add to config.json"
        log_error(msg)
        return False

    url    = f"{GRAPH_API_BASE}/me/permissions"
    params = {"access_token": token}

    try:
        response = requests.get(url, params=params, timeout=15)
    except requests.exceptions.ConnectionError:
        msg = "Connection failed — check internet connectivity"
        log_error(msg)
        return False
    except requests.exceptions.Timeout:
        msg = "Meta API request timed out after 15 seconds"
        log_error(msg)
        return False
    except Exception as e:
        msg = f"Unexpected request error: {e}"
        log_error(msg)
        return False

    # Handle HTTP errors
    if response.status_code == 401:
        msg = "Access token is invalid or expired. Generate a new Long-Lived Token."
        log_error(msg)
        return False

    if response.status_code == 429:
        msg = "Meta API rate limit reached. Wait before retrying."
        log_error(msg)
        return False

    if response.status_code != 200:
        msg = f"Meta API returned status {response.status_code}: {response.text[:300]}"
        log_error(msg)
        return False

    # Parse permissions
    try:
        data = response.json()
    except Exception:
        msg = "Failed to parse Meta API response as JSON"
        log_error(msg)
        return False

    permissions = data.get("data", [])
    if not permissions:
        msg = "No permissions returned from Meta API"
        log_error(msg)
        return False

    # Build granted set
    granted = {
        p["permission"]
        for p in permissions
        if p.get("status") == "granted"
    }

    log("-" * 55)
    log("Permissions returned by Meta:")
    for p in permissions:
        name   = p.get("permission", "unknown")
        status = p.get("status", "unknown")
        level  = "OK" if status == "granted" else "WARN"
        log(f"  {name:<45} {status.upper()}", level)

    log("-" * 55)

    all_present = True
    for scope in REQUIRED_SCOPES:
        if scope in granted:
            log(f"  {scope} -- GRANTED", "OK")
        else:
            log(f"  {scope} -- MISSING OR NOT GRANTED", "WARN")
            log_error(f"Required scope missing: {scope}")
            all_present = False

    log("-" * 55)
    if all_present:
        log("All required permissions verified. Ready to publish.", "OK")
    else:
        log("One or more required permissions are missing.", "WARN")
        log("Submit your app for Meta review to activate these scopes.", "INFO")
    log("=" * 55)

    return all_present


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClipFarmer -- Meta Scope Verifier")
    parser.add_argument("--token", default="", help="Override access token for testing")
    args = parser.parse_args()

    result = verify_meta_scopes(token=args.token)
    sys.exit(0 if result else 1)
