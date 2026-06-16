"""
brain_updater.py — ClipFarmer Self-Optimization Engine v2.0
Reads analytics data, scores hook performance, and updates hook weights automatically.

Usage:
  python brain_updater.py --status       # Show current brain state
  python brain_updater.py --report       # Input new analytics data
  python brain_updater.py --optimize     # Run automatic hook weight optimization
  python brain_updater.py --reset        # Reset all weights to default
"""

import json
import argparse
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import datetime

BASE_DIR     = Path("C:/clipfarmer")
ANALYTICS_FILE = BASE_DIR / "analytics.json"
HOOKS_FILE     = BASE_DIR / "hooks.json"
BRAIN_FILE     = BASE_DIR / "brain.json"

# ── Thresholds ────────────────────────────────────────────────────────────────
LOW_RETENTION_THRESHOLD  = 40.0   # Below this → flag and reduce weight
HIGH_RETENTION_THRESHOLD = 70.0   # Above this → boost weight
WEIGHT_BOOST  = 1.5
WEIGHT_REDUCE = 0.6
WEIGHT_MIN    = 0.1
WEIGHT_MAX    = 5.0

# ── Default templates ─────────────────────────────────────────────────────────

DEFAULT_ANALYTICS = {
    "last_updated": "",
    "total_clips_analyzed": 0,
    "entries": []
}

ANALYTICS_ENTRY_TEMPLATE = {
    "video_id":              "",
    "niche":                 "",
    "hook_used":             "",
    "watch_time_percentage": 0.0,
    "gumroad_clicks":        0,
    "views":                 0,
    "likes":                 0,
    "date":                  ""
}

DEFAULT_HOOKS = {
    "version": "2.0",
    "last_optimized": "",
    "niches": {
        "motivational": {
            "hooks": [
                {"text": "unreal aura",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "let him cook",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "no cap fr",             "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "built different",       "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "main character",        "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "lowkey inspiring fr",   "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "real ones know",        "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "this hits different",   "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "silent grind era",      "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "accountability check",  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
            ]
        },
        "satisfying": {
            "hooks": [
                {"text": "cured my anxiety",      "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "lowkey healing",         "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "so satisfying fr",       "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "brain reset",            "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "oddly okay",             "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "serotonin unlocked",     "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "this is so clean fr",    "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "my ocd is happy",        "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "therapy but free",       "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "watch time guaranteed",  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
            ]
        },
        "animals": {
            "hooks": [
                {"text": "the audacity",           "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "feral behavior",         "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "unhinged fr",            "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "not the vibe",           "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "chaotic good",           "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "infinite rizz",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "delulu but iconic",      "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "no thoughts head empty", "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "he understood nothing",  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "animal arc unlocked",    "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
            ]
        },
        "facts": {
            "hooks": [
                {"text": "bro what",               "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "actually wild",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "lowkey cursed",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "they hid this fr",       "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "fr tho",                 "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "school never told us",   "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "i am not okay",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "rent free in my brain",  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "brainrot unlocked",      "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "this changes everything","weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
            ]
        },
        "hacks": {
            "hooks": [
                {"text": "why didnt i know",       "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "game changer fr",        "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "actually goated",        "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "life unlocked",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "save this immediately",  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "npc behaviour fixed",    "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "cheat code activated",   "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "they gatekept this",     "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "actually useful fr",     "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "efficiency arc begins",  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
            ]
        },
        "default": {
            "hooks": [
                {"text": "wait for it",            "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "no cap",                 "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "lowkey unreal",          "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "fr fr",                  "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
                {"text": "actually insane",        "weight": 1.0, "uses": 0, "avg_retention": 0.0, "flag": ""},
            ]
        }
    }
}

DEFAULT_BRAIN = {
    "version": "2.0",
    "last_updated": "",
    "channel": {
        "name": "kenisterjz",
        "platform": "youtube",
        "started": "2026-06-14",
        "total_clips_posted": 0,
        "total_views": 0,
        "subscribers": 0
    },
    "niche_performance": {
        "satisfying":   {"clips_posted": 0, "total_views": 0, "avg_views": 0, "blocked_count": 0, "score": 0},
        "animals":      {"clips_posted": 0, "total_views": 0, "avg_views": 0, "blocked_count": 0, "score": 0},
        "facts":        {"clips_posted": 0, "total_views": 0, "avg_views": 0, "blocked_count": 0, "score": 0},
        "motivational": {"clips_posted": 0, "total_views": 0, "avg_views": 0, "blocked_count": 0, "score": 0},
        "hacks":        {"clips_posted": 0, "total_views": 0, "avg_views": 0, "blocked_count": 0, "score": 0},
    },
    "weekly_reports": [],
    "blocked_sources": [],
    "winning_hooks": [],
    "underperforming_hooks": []
}


# ── File helpers ──────────────────────────────────────────────────────────────

def log(message: str, level: str = "INFO"):
    icons = {"INFO": ">>", "OK": "OK", "WARN": "!!", "ERR": "XX", "BRAIN": "**"}
    icon = icons.get(level, ">>")
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {icon}  {message}", flush=True)


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        save_json(path, default)
        log(f"Created default file: {path.name}", "OK")
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        log(f"Corrupted JSON detected in {path.name} — restoring default", "WARN")
        save_json(path, default)
        return default


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Core functions ────────────────────────────────────────────────────────────

def verify_files():
    """Ensure all required JSON files exist with correct structure."""
    log("Verifying data files...", "INFO")
    load_json(ANALYTICS_FILE, DEFAULT_ANALYTICS)
    load_json(HOOKS_FILE, DEFAULT_HOOKS)
    load_json(BRAIN_FILE, DEFAULT_BRAIN)
    log("All data files verified", "OK")


def show_status():
    """Print current brain state to stdout."""
    brain    = load_json(BRAIN_FILE, DEFAULT_BRAIN)
    hooks    = load_json(HOOKS_FILE, DEFAULT_HOOKS)
    analytics = load_json(ANALYTICS_FILE, DEFAULT_ANALYTICS)

    ch = brain["channel"]
    log("=" * 52, "INFO")
    log("ClipFarmer Brain — System Status", "BRAIN")
    log("=" * 52, "INFO")
    log(f"Channel          : {ch['name']}", "INFO")
    log(f"Total clips      : {ch['total_clips_posted']}", "INFO")
    log(f"Total views      : {ch['total_views']:,}", "INFO")
    log(f"Subscribers      : {ch['subscribers']}", "INFO")
    log(f"Analytics entries: {analytics.get('total_clips_analyzed', 0)}", "INFO")
    log("", "INFO")
    log("Niche Scores:", "INFO")

    niches = brain.get("niche_performance", {})
    sorted_niches = sorted(niches.items(), key=lambda x: x[1]["score"], reverse=True)
    for niche, data in sorted_niches:
        bar = "█" * min(int(data["score"] / 10), 20)
        log(
            f"  {niche:<14} {bar:<20} "
            f"{data['score']} pts | {data['clips_posted']} clips | "
            f"{data['avg_views']:,} avg views",
            "INFO"
        )

    log("", "INFO")
    log("Hook Performance Summary:", "INFO")
    winners = brain.get("winning_hooks", [])
    losers  = brain.get("underperforming_hooks", [])
    log(f"  High performers  : {len(winners)} hooks", "OK")
    log(f"  Low performers   : {len(losers)} hooks", "WARN")

    if winners:
        log(f"  Top hook         : {winners[0].get('text', 'N/A')} "
            f"({winners[0].get('avg_retention', 0):.1f}% retention)", "OK")
    log("=" * 52, "INFO")


def run_optimization():
    """
    Core optimization loop:
    - Score all hooks against analytics retention data
    - Boost high performers, reduce low performers
    - Update hooks.json and brain.json
    """
    log("Starting hook weight optimization...", "BRAIN")

    analytics = load_json(ANALYTICS_FILE, DEFAULT_ANALYTICS)
    hooks     = load_json(HOOKS_FILE, DEFAULT_HOOKS)
    brain     = load_json(BRAIN_FILE, DEFAULT_BRAIN)

    entries = analytics.get("entries", [])

    if not entries:
        log("No analytics entries found — optimization skipped", "WARN")
        log("Add analytics data via --report to enable optimization", "INFO")
        return

    # Build retention map: {niche: {hook_text: [retention_scores]}}
    retention_map: dict[str, dict[str, list]] = {}
    for entry in entries:
        niche = entry.get("niche", "default")
        hook  = entry.get("hook_used", "")
        ret   = entry.get("watch_time_percentage", 0.0)
        if not hook:
            continue
        retention_map.setdefault(niche, {}).setdefault(hook, []).append(ret)

    winners    = []
    losers     = []
    boosted    = 0
    reduced    = 0
    unchanged  = 0

    niche_data = hooks.get("niches", {})

    for niche, hook_list_obj in niche_data.items():
        hook_list = hook_list_obj.get("hooks", [])
        niche_retention = retention_map.get(niche, {})

        for hook in hook_list:
            text   = hook.get("text", "")
            scores = niche_retention.get(text, [])

            if scores:
                avg = sum(scores) / len(scores)
                hook["uses"]          = hook.get("uses", 0) + len(scores)
                hook["avg_retention"] = round(avg, 1)

                if avg >= HIGH_RETENTION_THRESHOLD:
                    old_w = hook["weight"]
                    hook["weight"] = round(min(hook["weight"] * WEIGHT_BOOST, WEIGHT_MAX), 2)
                    hook["flag"]   = "high_performer"
                    winners.append({"text": text, "niche": niche, "avg_retention": avg})
                    boosted += 1
                    log(
                        f"  BOOST  [{niche}] '{text}' "
                        f"{old_w:.1f} → {hook['weight']:.1f} "
                        f"({avg:.1f}% retention)",
                        "OK"
                    )

                elif avg < LOW_RETENTION_THRESHOLD:
                    old_w = hook["weight"]
                    hook["weight"] = round(max(hook["weight"] * WEIGHT_REDUCE, WEIGHT_MIN), 2)
                    hook["flag"]   = "low_performer"
                    losers.append({"text": text, "niche": niche, "avg_retention": avg})
                    reduced += 1
                    log(
                        f"  REDUCE [{niche}] '{text}' "
                        f"{old_w:.1f} → {hook['weight']:.1f} "
                        f"({avg:.1f}% retention)",
                        "WARN"
                    )
                else:
                    hook["flag"] = ""
                    unchanged += 1
            else:
                unchanged += 1

    # Save updated hooks
    hooks["last_optimized"] = datetime.now().isoformat()
    save_json(HOOKS_FILE, hooks)

    # Update brain
    brain["last_updated"]          = datetime.now().isoformat()
    brain["winning_hooks"]         = sorted(winners, key=lambda x: x["avg_retention"], reverse=True)
    brain["underperforming_hooks"] = sorted(losers,   key=lambda x: x["avg_retention"])
    save_json(BRAIN_FILE, brain)

    log("", "INFO")
    log("=" * 52, "INFO")
    log("Optimization Complete", "BRAIN")
    log(f"  Hooks boosted    : {boosted}", "OK")
    log(f"  Hooks reduced    : {reduced}", "WARN")
    log(f"  Hooks unchanged  : {unchanged}", "INFO")
    log(f"  hooks.json saved : {HOOKS_FILE}", "OK")
    log("=" * 52, "INFO")


def input_report():
    """Interactive analytics data entry."""
    analytics = load_json(ANALYTICS_FILE, DEFAULT_ANALYTICS)

    log("Analytics Data Entry", "BRAIN")
    log("Format: niche,hook_used,watch_time_%,gumroad_clicks,views", "INFO")
    log("Example: motivational,let him cook,72,3,1200", "INFO")
    log("Type DONE when finished.", "INFO")
    log("", "INFO")

    new_entries = []
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if line.upper() == "DONE":
            break
        if not line:
            continue
        try:
            parts = [p.strip() for p in line.split(",")]
            entry = {
                "video_id":              f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "niche":                 parts[0],
                "hook_used":             parts[1],
                "watch_time_percentage": float(parts[2]),
                "gumroad_clicks":        int(parts[3]) if len(parts) > 3 else 0,
                "views":                 int(parts[4]) if len(parts) > 4 else 0,
                "likes":                 int(parts[5]) if len(parts) > 5 else 0,
                "date":                  datetime.now().strftime("%Y-%m-%d"),
            }
            new_entries.append(entry)
            log(
                f"Logged: [{entry['niche']}] '{entry['hook_used']}' "
                f"— {entry['watch_time_percentage']}% retention, "
                f"{entry['gumroad_clicks']} clicks",
                "OK"
            )
        except (IndexError, ValueError) as e:
            log(f"Invalid format — skipping: {e}", "WARN")

    if new_entries:
        analytics["entries"].extend(new_entries)
        analytics["total_clips_analyzed"] = len(analytics["entries"])
        analytics["last_updated"] = datetime.now().isoformat()
        save_json(ANALYTICS_FILE, analytics)
        log(f"Saved {len(new_entries)} new entries to analytics.json", "OK")
        log("Run --optimize to update hook weights", "INFO")
    else:
        log("No entries added", "WARN")


def update_niche_stats(niche: str, views: int, clips: int, blocked: int = 0):
    """Update brain.json niche performance scores."""
    brain = load_json(BRAIN_FILE, DEFAULT_BRAIN)
    np    = brain.get("niche_performance", {})

    if niche not in np:
        np[niche] = {"clips_posted": 0, "total_views": 0, "avg_views": 0,
                     "blocked_count": 0, "score": 0}

    nd = np[niche]
    nd["clips_posted"]  += clips
    nd["total_views"]   += views
    nd["blocked_count"] += blocked
    nd["avg_views"]      = nd["total_views"] // max(nd["clips_posted"], 1)
    nd["score"]          = nd["avg_views"] - (nd["blocked_count"] * 50)

    brain["niche_performance"] = np
    brain["channel"]["total_views"]       += views
    brain["channel"]["total_clips_posted"] += clips
    brain["last_updated"] = datetime.now().isoformat()

    save_json(BRAIN_FILE, brain)
    log(f"Niche '{niche}' updated: {nd['avg_views']} avg views, score {nd['score']}", "OK")


def reset_weights():
    """Reset all hook weights to 1.0."""
    hooks = load_json(HOOKS_FILE, DEFAULT_HOOKS)
    count = 0
    for niche_data in hooks.get("niches", {}).values():
        for hook in niche_data.get("hooks", []):
            hook["weight"]        = 1.0
            hook["flag"]          = ""
            hook["avg_retention"] = 0.0
    hooks["last_optimized"] = datetime.now().isoformat()
    save_json(HOOKS_FILE, hooks)
    log(f"All hook weights reset to 1.0", "OK")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClipFarmer Brain Optimizer")
    parser.add_argument("--status",   action="store_true", help="Show brain state")
    parser.add_argument("--report",   action="store_true", help="Input analytics data")
    parser.add_argument("--optimize", action="store_true", help="Run hook weight optimization")
    parser.add_argument("--reset",    action="store_true", help="Reset all weights to default")
    parser.add_argument("--niche",    type=str,            help="Niche name for --update")
    parser.add_argument("--views",    type=int, default=0, help="Views to log for niche")
    parser.add_argument("--clips",    type=int, default=0, help="Clips to log for niche")
    parser.add_argument("--blocked",  type=int, default=0, help="Blocked clips to log")
    args = parser.parse_args()

    verify_files()

    if args.status:
        show_status()

    elif args.report:
        input_report()

    elif args.optimize:
        run_optimization()

    elif args.reset:
        reset_weights()

    elif args.niche and (args.views or args.clips):
        update_niche_stats(args.niche, args.views, args.clips, args.blocked)

    else:
        show_status()

    log("[Brain Update Complete] Hook weights optimized based on latest analytics data", "BRAIN")