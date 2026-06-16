"""
downloader.py — ClipFarmer Phase 1
Downloads videos via yt-dlp with metadata logging.
"""

import os
import json
import uuid
import logging
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

import yt_dlp

from utils import load_config, update_job, get_video_duration, sanitize_filename

logger = logging.getLogger("clipfarmer.downloader")


class ClipDownloader:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.download_dir = Path(self.config["paths"]["downloads"])
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.min_dur = self.config["download"]["min_duration_seconds"]
        self.max_dur = self.config["download"]["max_duration_seconds"]
        self.quality = self.config["download"]["preferred_quality"]
        self.rate_limit = self.config["download"]["rate_limit"]

    def _ydl_opts(self, output_dir: Path, job_id: str) -> dict:
        return {
            "format": self.quality,
            "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
            "ratelimit": self._parse_rate(self.rate_limit),
            "noplaylist": True,
            "merge_output_format": "mp4",
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
            "quiet": False,
            "no_warnings": False,
            "progress_hooks": [self._make_progress_hook(job_id)],
            "match_filter": self._duration_filter(),
            "ffmpeg_location": str(Path(self.config["paths"]["ffmpeg"]).parent),
        }

    def _parse_rate(self, rate_str: str) -> int:
        """Convert '5M' -> 5242880 bytes"""
        multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3}
        if rate_str[-1].upper() in multipliers:
            return int(rate_str[:-1]) * multipliers[rate_str[-1].upper()]
        return int(rate_str)

    def _duration_filter(self):
        def _filter(info, *, incomplete):
            dur = info.get("duration")
            if dur is None:
                return None  # allow if unknown
            if dur < self.min_dur:
                return f"Video too short ({dur}s < {self.min_dur}s)"
            if dur > self.max_dur:
                return f"Video too long ({dur}s > {self.max_dur}s)"
            return None
        return _filter

    def _make_progress_hook(self, job_id: str):
        def _hook(d):
            if d["status"] == "downloading":
                pct = d.get("_percent_str", "?").strip()
                speed = d.get("_speed_str", "?").strip()
                logger.info(f"[{job_id[:8]}] Downloading: {pct} @ {speed}")
            elif d["status"] == "finished":
                logger.info(f"[{job_id[:8]}] Download finished: {d['filename']}")
                update_job(job_id, {
                    "download_path": d["filename"],
                    "download_status": "complete",
                    "downloaded_at": datetime.utcnow().isoformat()
                }, self.config["paths"]["jobs_db"])
            elif d["status"] == "error":
                logger.error(f"[{job_id[:8]}] Download error")
                update_job(job_id, {"download_status": "error"},
                           self.config["paths"]["jobs_db"])
        return _hook

    def download(self, url: str, job_id: Optional[str] = None) -> dict:
        """
        Download a single URL. Returns job dict with path and metadata.
        """
        if not job_id:
            job_id = str(uuid.uuid4())

        job_dir = self.download_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        job = {
            "id": job_id,
            "url": url,
            "created_at": datetime.utcnow().isoformat(),
            "download_status": "pending",
            "process_status": "pending",
            "download_path": None,
            "processed_path": None,
            "title": None,
            "duration": None,
            "error": None,
        }
        update_job(job_id, job, self.config["paths"]["jobs_db"])

        opts = self._ydl_opts(job_dir, job_id)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "unknown")
                duration = info.get("duration", 0)

                # Find the downloaded mp4
                downloaded_files = list(job_dir.glob("*.mp4"))
                if not downloaded_files:
                    downloaded_files = list(job_dir.glob("*.*"))

                if not downloaded_files:
                    raise FileNotFoundError(f"No output file found in {job_dir}")

                output_path = str(downloaded_files[0])

                update_job(job_id, {
                    "title": title,
                    "duration": duration,
                    "download_path": output_path,
                    "download_status": "complete",
                }, self.config["paths"]["jobs_db"])

                logger.info(f"✅ Downloaded: {title} ({duration}s) -> {output_path}")
                return {"job_id": job_id, "path": output_path, "title": title,
                        "duration": duration, "status": "ok"}

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Download failed for {url}: {error_msg}")
            update_job(job_id, {
                "download_status": "error",
                "error": error_msg
            }, self.config["paths"]["jobs_db"])
            return {"job_id": job_id, "path": None, "status": "error", "error": error_msg}

    def download_batch(self, urls: list[str]) -> list[dict]:
        """Download a list of URLs sequentially."""
        results = []
        for i, url in enumerate(urls, 1):
            logger.info(f"--- Batch {i}/{len(urls)}: {url}")
            result = self.download(url)
            results.append(result)
            if i < len(urls):
                time.sleep(1.5)  # polite delay
        return results

    def get_video_info(self, url: str) -> Optional[dict]:
        """Fetch metadata without downloading."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return {
                    "title": info.get("title"),
                    "duration": info.get("duration"),
                    "uploader": info.get("uploader"),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "upload_date": info.get("upload_date"),
                    "url": url,
                }
        except Exception as e:
            logger.error(f"Info fetch failed: {e}")
            return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    downloader = ClipDownloader()

    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"\n🎯 Downloading: {url}\n")
        result = downloader.download(url)
        print(f"\n{'✅ Done' if result['status'] == 'ok' else '❌ Failed'}: {result}")
    else:
        print("Usage: python downloader.py <youtube_url>")
        print("Example: python downloader.py https://www.youtube.com/watch?v=dQw4w9WgXcQ")
