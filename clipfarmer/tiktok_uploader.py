"""
ClipFarmer TikTok Uploader - v1.1.0
Reads credentials from config.json under the "tiktok" key.
"""

import json
import os
import sys
import time
import requests
from datetime import datetime


def load_config(config_path: str) -> dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"[CONFIG] Not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    if "tiktok" not in config:
        raise KeyError("[CONFIG] Missing 'tiktok' block in config.json")
    tiktok = config["tiktok"]
    for key in ["access_token", "video_path"]:
        if key not in tiktok:
            raise KeyError(f"[CONFIG] Missing '{key}' in config.tiktok")
    return tiktok


def log(level: str, message: str):
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [{level.upper()}] {message}", flush=True)


class TikTokUploader:

    CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
    UPLOAD_INIT_URL  = "https://open.tiktokapis.com/v2/post/publish/video/init/"

    RATE_LIMIT_CALLS  = 6
    RATE_LIMIT_WINDOW = 60
    UPLOAD_URL_TTL    = 3600

    def __init__(self, access_token: str, video_path: str, channel_id: str = "ch_01"):
        self.access_token = access_token
        self.video_path   = video_path
        self.channel_id   = channel_id

        self._call_timestamps: list = []
        self._upload_url: str = None
        self._publish_id: str = None
        self._upload_url_fetched_at: float = None

    def _base_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    def _enforce_rate_limit(self):
        now = time.time()
        self._call_timestamps = [t for t in self._call_timestamps if now - t < self.RATE_LIMIT_WINDOW]
        if len(self._call_timestamps) >= self.RATE_LIMIT_CALLS:
            oldest = self._call_timestamps[0]
            wait = self.RATE_LIMIT_WINDOW - (now - oldest)
            if wait > 0:
                log("WARN", f"[{self.channel_id}] Rate limit hit. Sleeping {wait:.1f}s ...")
                time.sleep(wait)
        self._call_timestamps.append(time.time())

    def _check_upload_url_expiry(self):
        if self._upload_url_fetched_at is None:
            return
        age = time.time() - self._upload_url_fetched_at
        if age >= self.UPLOAD_URL_TTL:
            raise RuntimeError(f"[{self.channel_id}] Upload URL expired. Re-run Tier 2.")

    def _get_video_size(self) -> int:
        if not os.path.exists(self.video_path):
            raise FileNotFoundError(f"[{self.channel_id}] Video not found: {self.video_path}")
        size = os.path.getsize(self.video_path)
        if size == 0:
            raise ValueError(f"[{self.channel_id}] Video file is empty.")
        return size

    def tier1_validate_creator(self) -> dict:
        log("INFO", f"[{self.channel_id}] TIER 1: Creator Profile Validation")
        self._enforce_rate_limit()
        try:
            response = requests.post(
                self.CREATOR_INFO_URL,
                headers=self._base_headers(),
                json={},
                timeout=30,
            )
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"TIER 1 connection failed: {e}")
        except requests.exceptions.Timeout:
            raise TimeoutError("TIER 1 timed out.")

        if response.status_code == 401:
            raise PermissionError("TIER 1: Access token expired or invalid.")
        if response.status_code != 200:
            raise RuntimeError(f"TIER 1 HTTP {response.status_code}: {response.text}")

        body = response.json()
        error_code = body.get("error", {}).get("code", "ok")
        if error_code != "ok":
            raise RuntimeError(f"TIER 1 API error: {error_code} - {body.get('error', {}).get('message')}")

        data = body.get("data", {})
        log("INFO", f"[{self.channel_id}] Creator: @{data.get('creator_username')} | {data.get('creator_nickname')}")
        return data

    def tier2_initialize_upload(self) -> tuple:
        log("INFO", f"[{self.channel_id}] TIER 2: Upload Initialization")
        file_size = self._get_video_size()
        log("INFO", f"[{self.channel_id}] File: {self.video_path} | Size: {file_size:,} bytes")
        self._enforce_rate_limit()

        payload = {
            "post_info": {
                "title":           "ClipFarmer Automated Review Demo #automation",
                "privacy_level":   "MUTUAL_FOLLOW_FRIENDS",
                "disable_duet":    False,
                "disable_stitch":  False,
                "disable_comment": False,
            },
            "source_info": {
                "source":            "FILE_UPLOAD",
                "video_size":        file_size,
                "chunk_size":        file_size,
                "total_chunk_count": 1,
            },
        }

        try:
            response = requests.post(
                self.UPLOAD_INIT_URL,
                headers=self._base_headers(),
                json=payload,
                timeout=30,
            )
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"TIER 2 connection failed: {e}")
        except requests.exceptions.Timeout:
            raise TimeoutError("TIER 2 timed out.")

        if response.status_code == 401:
            raise PermissionError("TIER 2: Access token expired.")
        if response.status_code != 200:
            raise RuntimeError(f"TIER 2 HTTP {response.status_code}: {response.text}")

        body = response.json()
        error_code = body.get("error", {}).get("code", "ok")
        if error_code != "ok":
            raise RuntimeError(f"TIER 2 API error: {error_code} - {body.get('error', {}).get('message')}")

        data       = body.get("data", {})
        upload_url = data.get("upload_url")
        publish_id = data.get("publish_id")

        if not upload_url or not publish_id:
            raise RuntimeError(f"TIER 2: Missing upload_url or publish_id. Response: {body}")

        self._upload_url            = upload_url
        self._publish_id            = publish_id
        self._upload_url_fetched_at = time.time()

        log("INFO", f"[{self.channel_id}] publish_id: {publish_id}")
        return upload_url, publish_id

    def tier3_upload_binary(self) -> bool:
        log("INFO", f"[{self.channel_id}] TIER 3: Binary Upload")
        if not self._upload_url:
            raise RuntimeError("TIER 3 called before TIER 2.")
        self._check_upload_url_expiry()

        file_size = self._get_video_size()
        upload_headers = {
            "Content-Type":   "video/mp4",
            "Content-Length": str(file_size),
            "Content-Range":  f"bytes 0-{file_size - 1}/{file_size}",
        }

        log("INFO", f"[{self.channel_id}] Uploading {file_size:,} bytes ...")
        try:
            with open(self.video_path, "rb") as video_file:
                response = requests.put(
                    self._upload_url,
                    headers=upload_headers,
                    data=video_file,
                    timeout=300,
                )
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(f"TIER 3 connection failed: {e}")
        except requests.exceptions.Timeout:
            raise TimeoutError("TIER 3 upload timed out.")

        if response.status_code not in (200, 201, 204):
            raise RuntimeError(f"TIER 3 HTTP {response.status_code}: {response.text[:500]}")

        log("INFO", f"[{self.channel_id}] Upload accepted. HTTP {response.status_code}")
        log("INFO", f"[{self.channel_id}] publish_id {self._publish_id} processing on TikTok.")
        return True

    def run(self) -> bool:
        log("INFO", f"[{self.channel_id}] === ClipFarmer Upload Pipeline START ===")
        try:
            self.tier1_validate_creator()
            self.tier2_initialize_upload()
            self.tier3_upload_binary()
            log("INFO", f"[{self.channel_id}] === COMPLETE — publish_id: {self._publish_id} ===")
            return True
        except (PermissionError, FileNotFoundError, ValueError) as e:
            log("ERROR", str(e))
            return False
        except (ConnectionError, TimeoutError) as e:
            log("ERROR", f"Network failure: {e}")
            return False
        except RuntimeError as e:
            log("ERROR", str(e))
            return False
        except Exception as e:
            log("ERROR", f"{type(e).__name__}: {e}")
            return False


if __name__ == "__main__":
    CONFIG_PATH = r"C:\clipfarmer\clipfarmer\config.json"

    try:
        tiktok_config = load_config(CONFIG_PATH)
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        log("FATAL", str(e))
        sys.exit(1)

    uploader = TikTokUploader(
        access_token=tiktok_config["access_token"],
        video_path=tiktok_config.get("video_path", r"C:\clipfarmer\storage\review_demo.mp4"),
        channel_id=tiktok_config.get("channel_id", "ch_01"),
    )

    success = uploader.run()
    sys.exit(0 if success else 1)