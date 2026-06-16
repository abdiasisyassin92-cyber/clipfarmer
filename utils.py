"""
utils.py — ClipFarmer shared utilities
"""

import json
import os
import re
import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clipfarmer.utils")


def load_config(config_path: str = "config.json") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jobs(db_path: str) -> dict:
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if not db.exists():
        return {}
    with open(db, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_jobs(jobs: dict, db_path: str):
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    with open(db, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)


def update_job(job_id: str, updates: dict, db_path: str):
    jobs = load_jobs(db_path)
    if job_id not in jobs:
        jobs[job_id] = {"id": job_id}
    jobs[job_id].update(updates)
    save_jobs(jobs, db_path)


def get_video_info_ffprobe(video_path: str, ffprobe_path: str) -> Optional[dict]:
    """Get video width, height, duration, has_audio via ffprobe."""
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding="utf-8")
        if result.returncode != 0:
            logger.error(f"ffprobe error: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            return None

        duration = float(fmt.get("duration", 0)) or float(video_stream.get("duration", 0))

        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "duration": duration,
            "has_audio": audio_stream is not None,
            "codec": video_stream.get("codec_name", "unknown"),
            "fps": eval(video_stream.get("r_frame_rate", "30/1")),
        }
    except Exception as e:
        logger.error(f"ffprobe exception: {e}")
        return None


def get_video_duration(video_path: str) -> float:
    """Quick duration check via ffprobe (requires ffprobe on PATH)."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, text=True, timeout=15
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def format_srt_time(seconds: float) -> str:
    """Convert seconds (float) to SRT timestamp: HH:MM:SS,mmm"""
    ms = int((seconds % 1) * 1000)
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def sanitize_filename(name: str) -> str:
    """Remove chars unsafe for filenames."""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip(". ")
    return name[:120] or "untitled"


def human_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


def seconds_to_hms(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h:
        return f"{h}h {m}m {s}s"
    elif m:
        return f"{m}m {s}s"
    return f"{s}s"
