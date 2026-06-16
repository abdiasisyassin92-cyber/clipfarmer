"""
pipeline.py — ClipFarmer Phase 1
Orchestrates download → transcribe → process for one or many URLs.
Run directly or import ClipPipeline into other scripts.
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from downloader import ClipDownloader
from processor import ClipProcessor
from utils import load_config, load_jobs, seconds_to_hms

# ─── Logging setup ────────────────────────────────────────────────────────────

def setup_logging(log_dir: str = "./logs", level: str = "INFO"):
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    fmt = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    logging.basicConfig(level=getattr(logging, level), format=fmt, handlers=handlers)
    return log_file


logger = logging.getLogger("clipfarmer.pipeline")


# ─── Pipeline class ───────────────────────────────────────────────────────────

class ClipPipeline:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.downloader = ClipDownloader(config_path)
        self.processor = ClipProcessor(config_path)

    def run_single(self, url: str) -> dict:
        """Full pipeline for one URL: download → transcribe → process."""
        start = time.time()
        logger.info("=" * 60)
        logger.info(f"🚀 Starting pipeline for: {url}")
        logger.info("=" * 60)

        # ── Download ──────────────────────────────────────────────────────────
        logger.info("📥 Phase 1: Downloading...")
        dl_result = self.downloader.download(url)

        if dl_result["status"] != "ok" or not dl_result.get("path"):
            logger.error(f"❌ Download failed: {dl_result.get('error')}")
            return {"url": url, "status": "download_failed", "error": dl_result.get("error")}

        job_id = dl_result["job_id"]
        video_path = dl_result["path"]
        title = dl_result.get("title", "Unknown")
        duration = dl_result.get("duration", 0)

        logger.info(f"✅ Downloaded: '{title}' ({seconds_to_hms(duration)})")

        # ── Process ───────────────────────────────────────────────────────────
        logger.info("⚙️ Phase 2: Processing (crop + captions + music)...")
        output_path = self.processor.process_full(video_path, job_id)

        elapsed = time.time() - start

        if not output_path:
            logger.error(f"❌ Processing failed for job {job_id}")
            return {
                "url": url,
                "job_id": job_id,
                "title": title,
                "status": "process_failed",
                "elapsed": elapsed,
            }

        logger.info("=" * 60)
        logger.info(f"🎉 Pipeline complete in {seconds_to_hms(elapsed)}")
        logger.info(f"📂 Output: {output_path}")
        logger.info("=" * 60)

        return {
            "url": url,
            "job_id": job_id,
            "title": title,
            "input": video_path,
            "output": output_path,
            "status": "complete",
            "elapsed": elapsed,
        }

    def run_batch(self, urls: list[str]) -> list[dict]:
        """Run pipeline for multiple URLs."""
        results = []
        total = len(urls)

        for i, url in enumerate(urls, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"📦 Job {i}/{total}")
            result = self.run_single(url)
            results.append(result)

            ok = sum(1 for r in results if r["status"] == "complete")
            fail = sum(1 for r in results if r["status"] != "complete")
            logger.info(f"Progress: {ok} ok, {fail} failed, {total - i} remaining")

        logger.info(f"\n{'='*60}")
        logger.info(f"🏁 Batch complete: {ok}/{total} successful")
        return results

    def status(self) -> dict:
        """Return a summary of all jobs."""
        jobs = load_jobs(self.config["paths"]["jobs_db"])
        total = len(jobs)
        complete = sum(1 for j in jobs.values()
                      if j.get("process_status") == "complete")
        failed = sum(1 for j in jobs.values()
                    if j.get("process_status") == "error" or
                       j.get("download_status") == "error")
        pending = total - complete - failed

        return {
            "total": total,
            "complete": complete,
            "failed": failed,
            "pending": pending,
            "jobs": list(jobs.values()),
        }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ClipFarmer — Viral Clip Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --url https://youtube.com/watch?v=xxxxx
  python pipeline.py --file urls.txt
  python pipeline.py --status
        """
    )
    parser.add_argument("--url", help="Single YouTube/video URL to process")
    parser.add_argument("--file", help="Text file with one URL per line")
    parser.add_argument("--config", default="config.json", help="Config file path")
    parser.add_argument("--status", action="store_true", help="Show job status summary")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = parser.parse_args()

    config = load_config(args.config)
    log_file = setup_logging(config["paths"]["logs"], args.log_level)
    logger.info(f"📋 Logging to: {log_file}")

    pipeline = ClipPipeline(args.config)

    if args.status:
        status = pipeline.status()
        print(f"\n{'='*40}")
        print(f"  ClipFarmer Job Status")
        print(f"{'='*40}")
        print(f"  Total:    {status['total']}")
        print(f"  Complete: {status['complete']} ✅")
        print(f"  Failed:   {status['failed']} ❌")
        print(f"  Pending:  {status['pending']} ⏳")
        print(f"{'='*40}\n")
        return

    if args.url:
        result = pipeline.run_single(args.url)
        print(f"\n{'✅' if result['status'] == 'complete' else '❌'} {result['status'].upper()}")
        if result.get("output"):
            print(f"📂 {result['output']}")
        sys.exit(0 if result["status"] == "complete" else 1)

    elif args.file:
        urls_file = Path(args.file)
        if not urls_file.exists():
            print(f"❌ File not found: {args.file}")
            sys.exit(1)
        urls = [line.strip() for line in urls_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")]
        if not urls:
            print("❌ No URLs found in file")
            sys.exit(1)
        print(f"📋 Loaded {len(urls)} URLs from {args.file}")
        results = pipeline.run_batch(urls)
        ok = sum(1 for r in results if r["status"] == "complete")
        print(f"\n🏁 Done: {ok}/{len(results)} clips processed")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
