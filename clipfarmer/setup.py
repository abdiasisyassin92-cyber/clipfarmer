"""
setup.py — ClipFarmer first-run setup
Run this once to verify your environment and create all required folders.
"""

import subprocess
import sys
import json
import shutil
from pathlib import Path


REQUIRED_PACKAGES = [
    "yt_dlp",
    "whisper",
    "moviepy",
]

DIRS = [
    "downloads",
    "processed",
    "music",
    "logs",
    "temp/captions",
]

BANNER = """
╔═══════════════════════════════════════════╗
║        ClipFarmer — Setup Check          ║
╚═══════════════════════════════════════════╝
"""


def check_python():
    major, minor = sys.version_info[:2]
    ok = major >= 3 and minor >= 10
    status = "✅" if ok else "❌"
    print(f"  {status} Python {major}.{minor} {'(ok)' if ok else '(need 3.10+)'}")
    return ok


def check_package(pkg_name: str) -> bool:
    try:
        __import__(pkg_name)
        print(f"  ✅ {pkg_name}")
        return True
    except ImportError:
        print(f"  ❌ {pkg_name} — not found. Run: pip install {pkg_name}")
        return False


def check_ffmpeg(ffmpeg_path: str) -> bool:
    p = Path(ffmpeg_path)
    if p.exists():
        print(f"  ✅ ffmpeg ({ffmpeg_path})")
        return True
    # Try system PATH
    found = shutil.which("ffmpeg")
    if found:
        print(f"  ✅ ffmpeg (system PATH: {found})")
        return True
    print(f"  ❌ ffmpeg not found at {ffmpeg_path} or on PATH")
    return False


def check_ffprobe(ffprobe_path: str) -> bool:
    p = Path(ffprobe_path)
    if p.exists():
        print(f"  ✅ ffprobe ({ffprobe_path})")
        return True
    found = shutil.which("ffprobe")
    if found:
        print(f"  ✅ ffprobe (system PATH: {found})")
        return True
    print(f"  ❌ ffprobe not found at {ffprobe_path} or on PATH")
    return False


def create_dirs():
    print("\n📁 Creating directories...")
    for d in DIRS:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"  ✅ ./{d}/")


def create_sample_urls():
    sample = Path("urls_sample.txt")
    if not sample.exists():
        sample.write_text(
            "# Add one YouTube/video URL per line\n"
            "# Lines starting with # are ignored\n"
            "# Example:\n"
            "# https://www.youtube.com/watch?v=dQw4w9WgXcQ\n",
            encoding="utf-8"
        )
        print(f"  ✅ Created urls_sample.txt (edit this with your URLs)")


def music_note():
    music_dir = Path("music")
    files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    if not files:
        print(f"\n🎵 Music: Drop royalty-free .mp3/.wav files into ./music/")
        print(f"   Suggested sources:")
        print(f"   - https://pixabay.com/music/")
        print(f"   - https://www.youtube.com/audiolibrary (download via yt-dlp)")
        print(f"   - https://freemusicarchive.org")
    else:
        print(f"\n🎵 Music: {len(files)} file(s) found in ./music/")


def main():
    print(BANNER)

    # Load config
    config_path = Path("config.json")
    if not config_path.exists():
        print("❌ config.json not found. Make sure you're in the clipfarmer/ directory.")
        sys.exit(1)

    with open(config_path) as f:
        config = json.load(f)

    all_ok = True

    print("🐍 Python:")
    all_ok &= check_python()

    print("\n📦 Packages:")
    for pkg in REQUIRED_PACKAGES:
        all_ok &= check_package(pkg)

    print("\n🔧 FFmpeg:")
    all_ok &= check_ffmpeg(config["paths"]["ffmpeg"])
    all_ok &= check_ffprobe(config["paths"]["ffprobe"])

    create_dirs()
    create_sample_urls()
    music_note()

    print("\n" + "─" * 45)
    if all_ok:
        print("✅ All checks passed. You're good to go!")
        print("\nQuick start:")
        print("  python pipeline.py --url <youtube_url>")
        print("  python pipeline.py --file urls_sample.txt")
        print("  python pipeline.py --status")
    else:
        print("⚠️  Some checks failed. Fix the issues above, then re-run setup.py")

    print("─" * 45 + "\n")


if __name__ == "__main__":
    main()
