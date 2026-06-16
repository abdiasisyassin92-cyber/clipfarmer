"""
youtube_uploader.py — ClipFarmer Phase 2
Auto-uploads processed clips to YouTube as Shorts.
Includes dynamic Gen Z title engine + niche-to-product Gumroad matching.
"""

import os
import json
import logging
import pickle
import random
from pathlib import Path
from datetime import datetime

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from utils import load_config, load_jobs, update_job

logger = logging.getLogger("clipfarmer.youtube")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_FILE = "youtube_token.pickle"
CLIENT_SECRETS = "client_secrets.json"


# ── Gen Z Dynamic Title Engine ────────────────────────────────────────────────

GENZ_TITLES = {
    "satisfying": {
        "hooks": [
            "this lowkey cured my anxiety...",
            "unreal satisfaction fr",
            "brain scratch compilation",
            "oddly okay with this",
            "my brain said thank you",
        ],
        "suffixes": [" (don't blink)", " (oddly satisfying)", " (no cap)", ""],
    },
    "animals": {
        "hooks": [
            "bro has infinite aura",
            "unreal animal moments",
            "he think he the main character",
            "the audacity of this creature",
            "feral behavior compilation",
        ],
        "suffixes": [" (mood)", " (flawless)", " (chaotic)", ""],
    },
    "hacks": {
        "hooks": [
            "gatekeeping this hack until now",
            "actually useful for once",
            "i was today years old",
            "why didnt anyone tell me",
            "game changer fr",
        ],
        "suffixes": [" (save this)", " (useful)", " (lowkey goated)", ""],
    },
    "facts": {
        "hooks": [
            "brainrot but make it smart",
            "no one talks about this rule",
            "unreal historical lore",
            "they hid this fr",
            "actually wild ngl",
        ],
        "suffixes": [" (wild)", " (fact check)", " (bro what)", ""],
    },
    "motivational": {
        "hooks": [
            "let him cook fr",
            "this hits different at 2am",
            "unreal mindset shift",
            "built different energy",
            "no excuses era",
        ],
        "suffixes": [" (grind)", " (real)", " (main character)", ""],
    },
    "default": {
        "hooks": [
            "lowkey unreal",
            "bro said no context needed",
            "you will send this to someone",
            "the internet found something",
            "actually insane ngl",
        ],
        "suffixes": [" (fr)", " (no cap)", ""],
    },
}


def generate_genz_title(niche: str) -> str:
    """
    Randomly picks a hook + suffix from the niche title pool,
    merges into a clean lowercase string under 60 chars + #shorts.
    """
    pool = GENZ_TITLES.get(niche, GENZ_TITLES["default"])
    hook = random.choice(pool["hooks"])
    suffix = random.choice(pool["suffixes"])
    base = f"{hook}{suffix}"
    title = f"{base} #shorts"
    # Hard cap at 97 chars (YouTube limit is 100, leave buffer)
    return title[:97]


# ── Gumroad Dynamic Product Map ───────────────────────────────────────────────

GUMROAD_PRODUCTS = {
    "motivational": {
        "url": "https://abdiassassin.gumroad.com/l/kkwmea",
        "hook": "get the ultimate entrepreneur + creator vault (save 30% 👇)",
    },
    "hacks": {
        "url": "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for content creators 👇",
    },
    "facts": {
        "url": "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for content creators 👇",
    },
    "satisfying": {
        "url": "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for content creators 👇",
    },
    "animals": {
        "url": "https://abdiassassin.gumroad.com/l/content-creator-prompts",
        "hook": "get 50 ai prompts for content creators 👇",
    },
    "default": {
        "url": "https://abdiassassin.gumroad.com",
        "hook": "get my ai prompt packs 👇",
    },
}


def get_product_cta(niche: str) -> str:
    product = GUMROAD_PRODUCTS.get(niche, GUMROAD_PRODUCTS["default"])
    return f"{product['hook']}\n{product['url']}"


def build_description(niche: str) -> str:
    cta = get_product_cta(niche)
    return f"{cta}\n\nfollow for more 🔥\n\n#shorts #viral #trending #fyp"


# ── Niche detection ───────────────────────────────────────────────────────────

NICHE_KEYWORDS = {
    "motivational": [
        "motivat", "resilience", "mindset", "grind", "success", "hustle",
        "inspire", "speech", "discipline", "winner", "champion", "wealthy",
        "rich think", "millionaire", "entrepreneur", "sigma",
    ],
    "satisfying": [
        "satisfying", "asmr", "oddly", "pressure wash", "kinetic", "sand",
        "soap", "cutting", "slime", "smooth", "clean", "rinse", "scrape",
    ],
    "animals": [
        "animal", "pet", "dog", "cat", "bird", "funny pet", "wildlife",
        "cute", "puppy", "kitten", "monkey", "bear",
    ],
    "facts": [
        "fact", "did you know", "mind blow", "science", "history", "psychology",
        "random", "knowledge", "truth", "secret", "actually", "learn",
    ],
    "hacks": [
        "hack", "tip", "trick", "life hack", "kitchen", "cleaning", "genius",
        "useful", "diy", "how to", "easy way", "secret method",
    ],
}

TAGS_BY_NICHE = {
    "motivational": ["motivation", "mindset", "success", "shorts", "viral", "fyp", "grind", "discipline"],
    "satisfying":   ["satisfying", "oddlysatisfying", "asmr", "shorts", "viral", "fyp", "relaxing"],
    "animals":      ["animals", "funnypets", "cute", "shorts", "viral", "fyp", "pets", "funny"],
    "facts":        ["facts", "didyouknow", "mindblowing", "shorts", "viral", "fyp", "knowledge"],
    "hacks":        ["lifehacks", "tips", "useful", "shorts", "viral", "fyp", "hacks", "diy"],
    "default":      ["shorts", "viral", "trending", "fyp", "foryou", "funny", "amazing", "mustwatch"],
}


def detect_niche(title: str) -> str:
    title_lower = title.lower()
    for niche, keywords in NICHE_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return niche
    return "default"


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_authenticated_service():
    creds = None

    if Path(TOKEN_FILE).exists():
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing YouTube token...")
            creds.refresh(Request())
        else:
            if not Path(CLIENT_SECRETS).exists():
                raise FileNotFoundError(f"Missing {CLIENT_SECRETS}")
            logger.info("Opening browser for YouTube authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
        logger.info("✅ YouTube token saved")

    return build("youtube", "v3", credentials=creds)


# ── Upload ────────────────────────────────────────────────────────────────────

def upload_short(video_path: str, title: str = None, job_id: str = None,
                 config_path: str = "config.json") -> dict:
    config = load_config(config_path)
    video_path = Path(video_path)

    if not video_path.exists():
        return {"status": "error", "error": f"File not found: {video_path}"}

    # Detect niche from source title
    raw_title = title or video_path.stem.replace("_final", "").replace("_", " ")
    niche = detect_niche(raw_title)

    # Generate Gen Z title + dynamic description
    yt_title = generate_genz_title(niche)
    description = build_description(niche)
    tags = TAGS_BY_NICHE.get(niche, TAGS_BY_NICHE["default"])

    logger.info(f"📤 Uploading to YouTube: {yt_title}")
    logger.info(f"   Niche: {niche}")
    logger.info(f"   Product CTA: {GUMROAD_PRODUCTS.get(niche, GUMROAD_PRODUCTS['default'])['url']}")
    logger.info(f"   File: {video_path} ({video_path.stat().st_size / 1e6:.1f} MB)")

    try:
        youtube = get_authenticated_service()

        body = {
            "snippet": {
                "title": yt_title,
                "description": description,
                "tags": tags,
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            }
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024
        )

        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                logger.info(f"   Upload progress: {pct}%")

        video_id = response["id"]
        url = f"https://youtube.com/shorts/{video_id}"
        logger.info(f"✅ Uploaded! {url}")

        if job_id:
            update_job(job_id, {
                "youtube_video_id": video_id,
                "youtube_url": url,
                "youtube_uploaded_at": datetime.utcnow().isoformat(),
                "youtube_title": yt_title,
                "youtube_niche": niche,
            }, config["paths"]["jobs_db"])

        return {
            "status": "ok",
            "video_id": video_id,
            "url": url,
            "title": yt_title,
            "niche": niche,
        }

    except HttpError as e:
        error_msg = f"YouTube API error {e.resp.status}: {e.content}"
        logger.error(f"❌ {error_msg}")
        if job_id:
            update_job(job_id, {"youtube_status": "error", "youtube_error": error_msg},
                       config["paths"]["jobs_db"])
        return {"status": "error", "error": error_msg}

    except Exception as e:
        logger.error(f"❌ Upload failed: {e}")
        return {"status": "error", "error": str(e)}


def upload_all_processed(config_path: str = "config.json") -> list:
    config = load_config(config_path)
    jobs = load_jobs(config["paths"]["jobs_db"])

    pending = [
        j for j in jobs.values()
        if j.get("process_status") == "complete"
        and j.get("processed_path")
        and not j.get("youtube_video_id")
    ]

    if not pending:
        logger.info("No new clips to upload.")
        return []

    logger.info(f"Found {len(pending)} clip(s) ready to upload")
    results = []

    for job in pending:
        result = upload_short(
            video_path=job["processed_path"],
            title=job.get("title"),
            job_id=job["id"],
            config_path=config_path,
        )
        results.append(result)

    ok = sum(1 for r in results if r["status"] == "ok")
    logger.info(f"✅ Uploaded {ok}/{len(results)} clips")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="ClipFarmer — YouTube Uploader")
    parser.add_argument("--file", help="Upload a specific video file")
    parser.add_argument("--title", help="Custom title for the video")
    parser.add_argument("--all", action="store_true",
                        help="Upload all processed clips not yet on YouTube")
    parser.add_argument("--auth", action="store_true",
                        help="Just authenticate, don't upload anything")
    parser.add_argument("--test-title", type=str,
                        help="Preview generated title for a given niche")
    args = parser.parse_args()

    if args.auth:
        print("🔐 Authenticating with YouTube...")
        svc = get_authenticated_service()
        print("✅ Authentication successful! Token saved.")
        sys.exit(0)

    if args.test_title:
        niche = args.test_title
        title = generate_genz_title(niche)
        desc = build_description(niche)
        print(f"\n Niche: {niche}")
        print(f" Title: {title}")
        print(f" Description:\n{desc}\n")
        sys.exit(0)

    if args.all:
        results = upload_all_processed()
        for r in results:
            print(f"{'✅' if r['status'] == 'ok' else '❌'} {r.get('url', r.get('error'))}")

    elif args.file:
        result = upload_short(args.file, title=args.title)
        if result["status"] == "ok":
            print(f"\n✅ Live on YouTube: {result['url']}")
            print(f"   Title: {result['title']}")
            print(f"   Niche: {result['niche']}")
        else:
            print(f"\n❌ Failed: {result['error']}")
    else:
        parser.print_help()