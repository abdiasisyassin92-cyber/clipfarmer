"""
cleanup.py — ClipFarmer Storage Maintenance
Deletes source clips and temp files older than 3 days.
Safe to run manually or on a schedule.

Usage:
  python cleanup.py           # Standard cleanup (3-day retention)
  python cleanup.py --dry-run # Preview what would be deleted without deleting
  python cleanup.py --days 1  # Custom retention period
"""

import os
import time
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [cleanup] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("cleanup")

BASE_DIR = Path("C:/clipfarmer")

TARGET_DIRS = [
    BASE_DIR / "downloads",
    BASE_DIR / "temp",
]


def format_size(bytes_count: int) -> str:
    if bytes_count >= 1_073_741_824:
        return f"{bytes_count / 1_073_741_824:.2f} GB"
    elif bytes_count >= 1_048_576:
        return f"{bytes_count / 1_048_576:.2f} MB"
    elif bytes_count >= 1024:
        return f"{bytes_count / 1024:.2f} KB"
    return f"{bytes_count} B"


def run_cleanup(retention_days: int = 3, dry_run: bool = False):
    cutoff = time.time() - (retention_days * 86400)
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    logger.info("=" * 55)
    logger.info("ClipFarmer Storage Maintenance")
    logger.info(f"Time         : {now_str}")
    logger.info(f"Retention    : {retention_days} days")
    logger.info(f"Mode         : {'DRY RUN — no files will be deleted' if dry_run else 'LIVE — deleting old files'}")
    logger.info("=" * 55)

    files_deleted = 0
    files_skipped = 0
    bytes_freed   = 0
    dirs_removed  = 0

    for target in TARGET_DIRS:
        if not target.exists():
            logger.info(f"Directory not found, skipping: {target}")
            continue

        logger.info(f"\nScanning: {target}")

        # Collect all files, sorted deepest first so dirs empty before we try to remove them
        all_files = sorted(target.rglob("*"), key=lambda p: len(p.parts), reverse=True)

        for path in all_files:
            if path.is_file():
                try:
                    mtime = path.stat().st_mtime
                    age_days = (time.time() - mtime) / 86400

                    if mtime < cutoff:
                        size = path.stat().st_size
                        if not dry_run:
                            path.unlink()
                        files_deleted += 1
                        bytes_freed += size
                        logger.info(
                            f"  {'[DRY]' if dry_run else '✅'} deleted: {path.name} "
                            f"({format_size(size)}, {age_days:.1f}d old)"
                        )
                    else:
                        files_skipped += 1

                except PermissionError:
                    logger.warning(f"  ⚠ locked (in use), skipping: {path.name}")
                except FileNotFoundError:
                    pass  # Already deleted by another process
                except Exception as e:
                    logger.warning(f"  ⚠ error on {path.name}: {e}")

            elif path.is_dir():
                # Remove directory if empty
                try:
                    if not any(path.iterdir()):
                        if not dry_run:
                            path.rmdir()
                        dirs_removed += 1
                        logger.info(f"  {'[DRY]' if dry_run else '🗂'} removed empty dir: {path.name}")
                except Exception:
                    pass

    logger.info("\n" + "=" * 55)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 55)
    logger.info(f"Files deleted    : {files_deleted}")
    logger.info(f"Files retained   : {files_skipped}")
    logger.info(f"Empty dirs removed: {dirs_removed}")
    logger.info(f"Space recovered  : {format_size(bytes_freed)}")
    if dry_run:
        logger.info("(dry run — nothing was actually deleted)")
    logger.info("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClipFarmer Storage Cleanup")
    parser.add_argument(
        "--days", type=int, default=3,
        help="Retention period in days (default: 3)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview deletions without actually deleting"
    )
    args = parser.parse_args()
    run_cleanup(retention_days=args.days, dry_run=args.dry_run)
