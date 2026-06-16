"""
scheduler.py — ClipFarmer Phase 2
Auto-finds trending videos, processes them, and posts to YouTube + Instagram.

Usage:
  python scheduler.py              # Run one full cycle now
  python scheduler.py --loop       # Run continuously (post every N hours)
  python scheduler.py --sources    # Just show what videos it found
"""

import time
import random
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import yt_dlp

from downloader import ClipDownloader
from processor import ClipProcessor
from utils import load_config, load_jobs, update_job, seconds_to_hms

logger = logging.getLogger("clipfarmer.scheduler")

# ── Safe dopamine sources only ────────────────────────────────────────────────
# Rules: user-generated, no studio IP, no branded channels, no sports footage
# Focus: satisfying, animals, facts, life hacks, motivation — all high watch time

SOURCES = [
    # Satisfying — highest watch time, almost never blocked
    ("oddly satisfying videos shorts 2025", 3),
    ("satisfying pressure washing shorts", 3),
    ("satisfying kinetic sand cutting", 2),
    ("soap cutting satisfying asmr", 2),
    ("most satisfying videos shorts", 2),
    ("satisfying factory machines shorts", 2),
    ("ice crushing satisfying shorts", 2),

    # Animals — user-generated, huge audience, safe
    ("funny animals shorts 2025", 3),
    ("cute animal moments viral shorts", 3),
    ("dog vs cat funny shorts", 2),
    ("animals being funny shorts", 2),
    ("unexpected animal behavior shorts", 2),

    # Life Hacks — original creators, safe
    ("life hacks that actually work 2025", 3),
    ("genius kitchen hacks shorts", 2),
    ("cleaning hacks satisfying shorts", 2),
    ("useful everyday tips shorts", 2),

    # Facts — text-based, safe, high shares
    ("fun facts you didnt know shorts", 3),
    ("mind blowing facts 60 seconds", 2),
    ("psychological facts viral shorts", 2),
    ("random facts that sound fake shorts", 2),

    # Motivational — speech clips, safe
    ("motivation shorts that hit different", 3),
    ("mindset shorts 2025", 2),
    ("discipline motivation shorts", 2),
]

# ── Skip anything with these in title or channel ──────────────────────────────
BLOCKED_KEYWORDS = [
    "documentary", "gopro", "news", "official", "movie", "film", "trailer",
    "nfl", "nba", "nhl", "mlb", "highlights", "match", "full game", "episode",
    "season", "netflix", "hbo", "bbc", "cnn", "fox", "anime", "amv", "edit",
    "bleach", "naruto", "dragon ball", "one piece", "jujutsu", "demon slayer",
    "my hero", "cartoon", "disney", "pixar", "marvel", "dc comics",
    "compilation by", "best of 2024", "best of 2023", "cyanide", "happiness",
]

BLOCKED_CHANNELS = [
    "gopro", "nfl", "nba", "espn", "bbc", "cnn", "foxnews",
    "nationalgeographic", "nat geo", "vice", "buzzfeed",
    "aaron's animals",  # licensed content
]


def is_safe(entry: dict) -> bool:
    title = (entry.get("title") or "").lower()
    channel = (entry.get("channel") or entry.get("uploader") or "").lower()
    for kw in BLOCKED_KEYWORDS:
        if kw in title:
            return False
    for ch in BLOCKED_CHANNELS:
        if ch in channel:
            return False
    return True


# ── Video search ──────────────────────────────────────────────────────────────

def search_videos(query: str, max_results: int = 3,
                  min_dur: int = 30, max_dur: int = 120) -> list[dict]:
    """Search YouTube. Max 120s — shorter = safer from copyright."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": max_results * 5,
        "ignoreerrors": True,
    }

    search_url = f"ytsearch{max_results * 5}:{query}"
    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            if not info:
                return []
            entries = info.get("entries") or []

            for entry in entries:
                if not entry:
                    continue
                dur = entry.get("duration") or 0
                if dur < min_dur or dur > max_dur:
                    continue
                if not is_safe(entry):
                    logger.info(f"   ⛔ Skipping: {entry.get('title', '')[:50]}")
                    continue
                vid_id = entry.get("id") or entry.get("url", "").split("v=")[-1]
                if not vid_id:
                    continue
                results.append({
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                    "title": entry.get("title", "Unknown"),
                    "duration": dur,
                    "view_count": entry.get("view_count") or 0,
                    "id": vid_id,
                })
                if len(results) >= max_results:
                    break

    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")

    return results


def find_trending_videos(n: int = 10) -> list[dict]:
    logger.info("🔍 Searching for trending videos...")
    all_videos = []
    seen_ids = set()

    try:
        config = load_config()
        jobs = load_jobs(config["paths"]["jobs_db"])
        seen_ids = {j.get("url", "").split("v=")[-1] for j in jobs.values()}
    except Exception:
        pass

    sources = random.sample(SOURCES, min(len(SOURCES), 12))

    for query, max_results in sources:
        logger.info(f"   Searching: {query}")
        videos = search_videos(query, max_results)
        for v in videos:
            if v["id"] not in seen_ids:
                all_videos.append(v)
                seen_ids.add(v["id"])
        time.sleep(1)

    all_videos.sort(key=lambda x: x["view_count"], reverse=True)
    selected = all_videos[:n]

    logger.info(f"✅ Found {len(selected)} fresh trending videos")
    for v in selected:
        views = f"{v['view_count']:,}" if v['view_count'] else "?"
        logger.info(f"   [{views} views] {v['title'][:60]}")

    return selected


# ── Full pipeline run ─────────────────────────────────────────────────────────

def run_cycle(n_videos: int = 3, post_youtube: bool = True,
              post_instagram: bool = False, config_path: str = "config.json"):
    start = time.time()
    logger.info("=" * 60)
    logger.info(f"🚀 ClipFarmer Auto-Cycle — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("=" * 60)

    videos = find_trending_videos(n_videos)
    if not videos:
        logger.warning("No videos found. Skipping cycle.")
        return []

    results = []
    downloader = ClipDownloader(config_path)
    processor = ClipProcessor(config_path)

    for i, video in enumerate(videos, 1):
        logger.info(f"\n[{i}/{len(videos)}] {video['title'][:60]}")

        dl = downloader.download(video["url"])
        if dl["status"] != "ok":
            logger.error(f"Download failed: {dl.get('error')}")
            results.append({"url": video["url"], "status": "download_failed"})
            continue

        output = processor.process_full(dl["path"], dl["job_id"])
        if not output:
            logger.error("Processing failed")
            results.append({"url": video["url"], "status": "process_failed"})
            continue

        result = {
            "url": video["url"],
            "title": video["title"],
            "job_id": dl["job_id"],
            "output": output,
            "status": "processed",
            "youtube": None,
            "instagram": None,
        }

        if post_youtube:
            try:
                from youtube_uploader import upload_short
                yt = upload_short(output, title=video["title"], job_id=dl["job_id"])
                result["youtube"] = yt
                if yt["status"] == "ok":
                    logger.info(f"✅ YouTube: {yt['url']} | niche: {yt.get('niche', '?')}")
                else:
                    logger.error(f"❌ YouTube: {yt.get('error')}")
            except Exception as e:
                logger.error(f"YouTube upload error: {e}")

        if post_instagram:
            try:
                from instagram_uploader import upload_reel
                ig = upload_reel(output, title=video["title"], job_id=dl["job_id"])
                result["instagram"] = ig
                if ig["status"] == "ok":
                    logger.info(f"✅ Instagram: {ig['url']}")
                else:
                    logger.error(f"❌ Instagram: {ig.get('error')}")
            except Exception as e:
                logger.error(f"Instagram upload error: {e}")

        results.append(result)

        if i < len(videos):
            logger.info("Waiting 30s before next video...")
            time.sleep(30)

    elapsed = time.time() - start
    ok = sum(1 for r in results if r["status"] == "processed")
    logger.info(f"\n{'='*60}")
    logger.info(f"🏁 Cycle complete in {seconds_to_hms(elapsed)}")
    logger.info(f"   Processed: {ok}/{len(videos)}")
    logger.info(f"{'='*60}")
    return results


# ── Loop mode ─────────────────────────────────────────────────────────────────

def run_loop(interval_hours: int = 6, videos_per_cycle: int = 3,
             post_youtube: bool = True, post_instagram: bool = False):
    logger.info(f"🔄 Loop mode: {videos_per_cycle} videos every {interval_hours}h")
    logger.info("Press Ctrl+C to stop\n")

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"\n⏰ Cycle #{cycle} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        try:
            run_cycle(
                n_videos=videos_per_cycle,
                post_youtube=post_youtube,
                post_instagram=post_instagram,
            )
        except KeyboardInterrupt:
            logger.info("\n👋 Stopped by user")
            break
        except Exception as e:
            logger.error(f"Cycle error: {e}")

        next_run = datetime.now() + timedelta(hours=interval_hours)
        logger.info(f"\n💤 Next cycle at {next_run.strftime('%H:%M')} ({interval_hours}h)")
        try:
            time.sleep(interval_hours * 3600)
        except KeyboardInterrupt:
            logger.info("\n👋 Stopped by user")
            break


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils import load_config
    import os

    config = load_config()
    log_dir = config.get("paths", {}).get("logs", "C:\\clipfarmer\\logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"scheduler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ]
    )

    parser = argparse.ArgumentParser(description="ClipFarmer Auto-Scheduler")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=6,
                        help="Hours between cycles (default: 6)")
    parser.add_argument("--videos", type=int, default=3,
                        help="Videos per cycle (default: 3)")
    parser.add_argument("--sources", action="store_true",
                        help="Show trending videos without downloading")
    parser.add_argument("--no-youtube", action="store_true",
                        help="Skip YouTube upload")
    parser.add_argument("--no-instagram", action="store_true",
                        help="Skip Instagram upload")
    args = parser.parse_args()

    post_yt = not args.no_youtube
    post_ig = not args.no_instagram

    if args.sources:
        videos = find_trending_videos(10)
        print(f"\n{'='*60}")
        print(f"Found {len(videos)} trending videos:")
        print(f"{'='*60}")
        for i, v in enumerate(videos, 1):
            views = f"{v['view_count']:,}" if v['view_count'] else "?"
            print(f"{i:2}. [{views:>12} views] {v['title'][:55]}")
            print(f"    {v['url']}")
        print()

    elif args.loop:
        run_loop(
            interval_hours=args.interval,
            videos_per_cycle=args.videos,
            post_youtube=post_yt,
            post_instagram=post_ig,
        )

    else:
        run_cycle(
            n_videos=args.videos,
            post_youtube=post_yt,
            post_instagram=post_ig,
        )