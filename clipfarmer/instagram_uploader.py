"""
instagram_uploader.py — ClipFarmer Phase 2
Publishes processed Reels to Instagram via the official Meta Graph API.
Requires: instagram_business_content_publish + instagram_business_basic permissions.

Setup:
  Add your Long-Lived Access Token and Instagram Business Account ID to
  C:\clipfarmer\config.json under the "instagram" key:
    "instagram": {
        "access_token": "YOUR_TOKEN",
        "account_id":   "YOUR_IG_BUSINESS_ACCOUNT_ID"
    }

Usage:
  python instagram_uploader.py --file clip.mp4 --video-url https://...
  python instagram_uploader.py --all
  python instagram_uploader.py --meta-review --video-url https://... --niche satisfying
  python instagram_uploader.py --test-caption --niche motivational
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
    import requests

from utils import load_config, load_jobs, update_job

logger = logging.getLogger("clipfarmer.instagram")

GRAPH_API_BASE   = "https://graph.facebook.com/v19.0"
MAX_POLL_RETRIES = 20
POLL_INTERVAL    = 8
CONFIG_FILE      = Path("C:/clipfarmer/config.json")
ERROR_LOG        = Path("C:/clipfarmer/logs/instagram_errors.log")
ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)

GUMROAD_PRODUCTS = {
    "motivational": {
        "url":  "https://abdiassassin.gumroad.com/l/kkwmea",
        "hook": "get the ultimate ai vault (save 30%)",
    },
    "hacks": {
        "url":  "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for creators",
    },
    "facts": {
        "url":  "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for creators",
    },
    "satisfying": {
        "url":  "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for creators",
    },
    "animals": {
        "url":  "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for creators",
    },
    "default": {
        "url":  "https://abdiassassin.gumroad.com",
        "hook": "get my ai prompt packs",
    },
}

NICHE_TAGS = {
    "motivational": "#motivation #mindset #success #shorts #viral #fyp #grind",
    "satisfying":   "#satisfying #oddlysatisfying #asmr #shorts #viral #fyp",
    "animals":      "#animals #funnypets #cute #shorts #viral #fyp #pets",
    "facts":        "#facts #didyouknow #mindblowing #shorts #viral #fyp",
    "hacks":        "#lifehacks #tips #useful #shorts #viral #fyp #hacks",
    "default":      "#shorts #viral #trending #fyp #foryou",
}

# ── Review mode flag (set by --meta-review CLI arg) ───────────────────────────
_REVIEW_MODE = False


def _log(message: str, level: str = "INFO"):
    """
    ASCII-safe logger. In review mode, outputs clean plain English descriptions
    with no symbols or technical strings that could confuse a Meta reviewer.
    """
    ts = datetime.now().strftime("%H:%M:%S")
    if _REVIEW_MODE:
        # Clean plain-English output for Meta reviewer inspection
        tag = {
            "INFO": "[ INFO ]",
            "OK":   "[  OK  ]",
            "WARN": "[  !!  ]",
            "ERR":  "[ FAIL ]",
            "STEP": "[ STEP ]",
        }.get(level, "[ INFO ]")
        print(f"[{ts}] {tag} {message}", flush=True)
    else:
        tag = {
            "INFO": "[Instagram] >>",
            "OK":   "[Instagram] OK",
            "WARN": "[Instagram] !!",
            "ERR":  "[Instagram] XX",
            "STEP": "[Instagram] --",
        }.get(level, "[Instagram] >>")
        print(f"[{ts}] {tag} {message}", flush=True)

    logger.info(message) if level not in ("ERR", "WARN") else logger.warning(message)


def _log_error(message: str):
    """Write error to log file and print to stdout."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except Exception:
        pass
    _log(message, "ERR")


# ── Credentials ───────────────────────────────────────────────────────────────

def get_credentials() -> tuple[str, str]:
    token      = os.environ.get("IG_ACCESS_TOKEN", "")
    account_id = os.environ.get("IG_ACCOUNT_ID", "")

    if not token or not account_id:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            ig         = cfg.get("instagram", {})
            token      = token      or ig.get("access_token", "")
            account_id = account_id or ig.get("account_id", "")
        except Exception:
            pass

    if not token:
        raise ValueError(
            "Instagram access token not found. "
            "Set IG_ACCESS_TOKEN env var or add instagram.access_token to config.json"
        )
    if not account_id:
        raise ValueError(
            "Instagram Business Account ID not found. "
            "Set IG_ACCOUNT_ID env var or add instagram.account_id to config.json"
        )

    return token, account_id


# ── Caption builder ───────────────────────────────────────────────────────────

def build_caption(niche: str = "default", title: str = "") -> str:
    product = GUMROAD_PRODUCTS.get(niche, GUMROAD_PRODUCTS["default"])
    tags    = NICHE_TAGS.get(niche, NICHE_TAGS["default"])
    return (
        f"{product['hook']} -> link in bio\n"
        f"{product['url']}\n\n"
        f"follow for more\n\n"
        f"{tags}"
    )


# ── Step 1: Create media container ────────────────────────────────────────────

def create_media_container(
    account_id: str,
    access_token: str,
    video_url: str,
    caption: str,
) -> str:
    if _REVIEW_MODE:
        _log("Step 1 of 3 -- Sending video information to Meta API to create a media container.", "STEP")
        _log(f"Target Instagram Business Account: {account_id}", "INFO")
        _log("Media type is set to REELS for short-form vertical video.", "INFO")
        _log("The video URL and caption are being transmitted securely over HTTPS.", "INFO")
    else:
        _log(f"Creating media container for account {account_id}...")

    url    = f"{GRAPH_API_BASE}/{account_id}/media"
    params = {
        "media_type":    "REELS",
        "video_url":     video_url,
        "caption":       caption,
        "share_to_feed": "true",
        "access_token":  access_token,
    }

    try:
        response = requests.post(url, data=params, timeout=30)
    except requests.exceptions.ConnectionError:
        msg = "Could not reach Meta API servers. Check internet connection."
        _log_error(msg)
        raise RuntimeError(msg)
    except requests.exceptions.Timeout:
        msg = "Meta API did not respond within 30 seconds. Will retry."
        _log_error(msg)
        raise RuntimeError(msg)

    if response.status_code == 400:
        msg = f"Meta API rejected the request. Likely an invalid video URL or missing permission. Details: {response.text[:300]}"
        _log_error(msg)
        raise RuntimeError(msg)

    if response.status_code == 429:
        msg = "Meta API rate limit reached. The application will pause before retrying."
        _log_error(msg)
        raise RuntimeError(msg)

    if response.status_code != 200:
        msg = f"Meta API returned an unexpected status code {response.status_code}. Details: {response.text[:300]}"
        _log_error(msg)
        raise RuntimeError(msg)

    data         = response.json()
    container_id = data.get("id")

    if not container_id:
        msg = f"Meta API did not return a container ID. Response: {data}"
        _log_error(msg)
        raise RuntimeError(msg)

    if _REVIEW_MODE:
        _log(f"Media container created successfully. Container ID received from Meta API.", "OK")
    else:
        _log(f"Container created: {container_id}", "OK")

    return container_id


# ── Step 2: Poll until container is ready ─────────────────────────────────────

def poll_container_status(container_id: str, access_token: str) -> bool:
    if _REVIEW_MODE:
        _log("Step 2 of 3 -- Waiting for Meta to finish processing the video file.", "STEP")
        _log("The application will check the processing status every 8 seconds.", "INFO")
        _log(f"Maximum wait time: {MAX_POLL_RETRIES * POLL_INTERVAL} seconds.", "INFO")
    else:
        _log(f"Polling container status: {container_id}")

    url    = f"{GRAPH_API_BASE}/{container_id}"
    params = {
        "fields":       "status_code,status",
        "access_token": access_token,
    }

    for attempt in range(1, MAX_POLL_RETRIES + 1):
        try:
            response = requests.get(url, params=params, timeout=15)
        except Exception as e:
            _log(f"Status check attempt {attempt} encountered a network error: {e}", "WARN")
            time.sleep(POLL_INTERVAL)
            continue

        if response.status_code != 200:
            _log(f"Status check returned code {response.status_code}. Retrying...", "WARN")
            time.sleep(POLL_INTERVAL)
            continue

        data        = response.json()
        status_code = data.get("status_code", "")
        status      = data.get("status", "")

        if _REVIEW_MODE:
            _log(f"Processing check {attempt} of {MAX_POLL_RETRIES} -- Current status: {status_code}", "INFO")
        else:
            _log(f"  Attempt {attempt}/{MAX_POLL_RETRIES} -- status: {status_code} ({status})")

        if status_code == "FINISHED":
            if _REVIEW_MODE:
                _log("Meta has finished processing the video. Ready to publish.", "OK")
            else:
                _log("Container processing complete", "OK")
            return True

        if status_code == "ERROR":
            msg = f"Meta reported a processing error for container {container_id}. Details: {data}"
            _log_error(msg)
            return False

        time.sleep(POLL_INTERVAL)

    msg = f"Video processing did not complete within the allowed wait time of {MAX_POLL_RETRIES * POLL_INTERVAL} seconds."
    _log_error(msg)
    return False


# ── Step 3: Publish ───────────────────────────────────────────────────────────

def publish_container(
    account_id: str,
    access_token: str,
    container_id: str,
) -> str:
    if _REVIEW_MODE:
        _log("Step 3 of 3 -- Sending the publish command to Meta API.", "STEP")
        _log("This step makes the Reel publicly visible on the Instagram profile.", "INFO")
    else:
        _log(f"Publishing container {container_id}...")

    url    = f"{GRAPH_API_BASE}/{account_id}/media_publish"
    params = {
        "creation_id":  container_id,
        "access_token": access_token,
    }

    try:
        response = requests.post(url, data=params, timeout=30)
    except Exception as e:
        msg = f"Publish request failed due to a network error: {e}"
        _log_error(msg)
        raise RuntimeError(msg)

    if response.status_code == 429:
        msg = "Meta API rate limit reached during publish. Please wait before retrying."
        _log_error(msg)
        raise RuntimeError(msg)

    if response.status_code != 200:
        msg = f"Meta API returned status {response.status_code} during publish. Details: {response.text[:300]}"
        _log_error(msg)
        raise RuntimeError(msg)

    data     = response.json()
    media_id = data.get("id")

    if not media_id:
        msg = f"Publish succeeded but no media ID was returned. Response: {data}"
        _log_error(msg)
        raise RuntimeError(msg)

    if _REVIEW_MODE:
        _log("Reel published successfully. The content is now live on Instagram.", "OK")
        _log(f"Instagram Media ID assigned by Meta: {media_id}", "OK")
    else:
        _log(f"Published successfully. Media ID: {media_id}", "OK")

    return media_id


# ── Main upload function ───────────────────────────────────────────────────────

def upload_reel(
    video_path: str = "",
    video_url: str = "",
    title: str = "",
    niche: str = "default",
    job_id: str = None,
    config_path: str = "config.json",
) -> dict:
    if _REVIEW_MODE:
        _log("=" * 55, "INFO")
        _log("ClipFarmer Instagram Reel Publisher", "INFO")
        _log("Official Meta Graph API Integration", "INFO")
        _log(f"Content niche: {niche}", "INFO")
        _log("=" * 55, "INFO")
    else:
        _log(f"Starting Reel upload | niche: {niche} | title: {title[:40]}")

    try:
        access_token, account_id = get_credentials()
        if _REVIEW_MODE:
            _log("Access credentials loaded successfully from local configuration.", "OK")
    except ValueError as e:
        _log_error(str(e))
        return {"status": "error", "error": str(e)}

    if not video_url:
        msg = "A public video URL is required. The Meta API cannot access local file paths."
        _log_error(msg)
        return {"status": "error", "error": msg}

    caption = build_caption(niche=niche, title=title)

    if _REVIEW_MODE:
        _log("Caption generated using niche-matched content strategy.", "INFO")

    try:
        container_id = create_media_container(
            account_id=account_id,
            access_token=access_token,
            video_url=video_url,
            caption=caption,
        )

        ready = poll_container_status(container_id, access_token)
        if not ready:
            msg = "Video processing did not complete. Upload aborted."
            _log_error(msg)
            if job_id:
                _save_job_result(job_id, "error", msg, config_path)
            return {"status": "error", "error": msg}

        media_id = publish_container(account_id, access_token, container_id)
        ig_url   = f"https://www.instagram.com/p/{media_id}/"

        if _REVIEW_MODE:
            _log("=" * 55, "INFO")
            _log("Upload process completed successfully.", "OK")
            _log(f"The Reel is now publicly available on Instagram.", "OK")
            _log("=" * 55, "INFO")
        else:
            _log(f"Reel live: {ig_url}", "OK")

        if job_id:
            _save_job_result(job_id, "ok", "", config_path, media_id=media_id, url=ig_url)

        return {
            "status":       "ok",
            "media_id":     media_id,
            "container_id": container_id,
            "url":          ig_url,
            "niche":        niche,
        }

    except RuntimeError as e:
        _log_error(f"Upload failed: {e}")
        if job_id:
            _save_job_result(job_id, "error", str(e), config_path)
        return {"status": "error", "error": str(e)}

    except Exception as e:
        _log_error(f"Unexpected error during upload: {e}")
        if job_id:
            _save_job_result(job_id, "error", str(e), config_path)
        return {"status": "error", "error": str(e)}


def _save_job_result(job_id, status, error, config_path, media_id="", url=""):
    try:
        config = load_config(config_path)
        data   = {
            "instagram_status":      status,
            "instagram_uploaded_at": datetime.utcnow().isoformat(),
        }
        if media_id:
            data["instagram_media_id"] = media_id
        if url:
            data["instagram_url"] = url
        if error:
            data["instagram_error"] = error
        update_job(job_id, data, config["paths"]["jobs_db"])
    except Exception:
        pass


def upload_all_processed(config_path: str = "config.json") -> list:
    config = load_config(config_path)
    jobs   = load_jobs(config["paths"]["jobs_db"])

    pending = [
        j for j in jobs.values()
        if j.get("process_status") == "complete"
        and j.get("processed_path")
        and not j.get("instagram_media_id")
        and j.get("instagram_video_url")
    ]

    if not pending:
        _log("No pending clips with public video URLs found")
        return []

    _log(f"Found {len(pending)} clip(s) ready for Instagram")
    results = []

    for job in pending:
        result = upload_reel(
            video_path=job["processed_path"],
            video_url=job["instagram_video_url"],
            title=job.get("title", ""),
            niche=job.get("youtube_niche", "default"),
            job_id=job["id"],
            config_path=config_path,
        )
        results.append(result)

    ok = sum(1 for r in results if r["status"] == "ok")
    _log(f"Uploaded {ok}/{len(results)} Reels", "OK" if ok == len(results) else "WARN")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    )

    parser = argparse.ArgumentParser(description="ClipFarmer -- Instagram Uploader")
    parser.add_argument("--file",          help="Local path to processed video file")
    parser.add_argument("--video-url",     help="Public HTTPS URL of the video", default="")
    parser.add_argument("--title",         help="Source video title", default="")
    parser.add_argument("--niche",         help="Content niche", default="default")
    parser.add_argument("--all",           action="store_true", help="Upload all pending clips")
    parser.add_argument("--test-caption",  action="store_true", help="Preview caption")
    parser.add_argument("--meta-review",   action="store_true",
                        help="Enable review mode: clean plain-English logs for Meta reviewer inspection")
    args = parser.parse_args()

    # Activate review mode globally
    if args.meta_review:
        _REVIEW_MODE = True

    if args.test_caption:
        cap = build_caption(niche=args.niche, title=args.title)
        print(f"\nNiche   : {args.niche}")
        print(f"Caption :\n{cap}\n")
        sys.exit(0)

    if args.all:
        results = upload_all_processed()
        for r in results:
            status = "OK" if r["status"] == "ok" else "FAIL"
            print(f"[{status}] {r.get('url', r.get('error', ''))}")

    elif args.video_url:
        result = upload_reel(
            video_path=args.file or "",
            video_url=args.video_url,
            title=args.title,
            niche=args.niche,
        )
        if result["status"] == "ok":
            print(f"\n[ OK ] Live on Instagram: {result['url']}")
        else:
            print(f"\n[FAIL] {result['error']}")

    else:
        parser.print_help()
        print("\nNote: --video-url is required. Meta API cannot access local file paths.")