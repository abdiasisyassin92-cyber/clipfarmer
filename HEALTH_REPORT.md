# ClipFarmer — Pipeline Health Report
Generated: 2026-06-16

## ✅ FIXED (auto-applied)
| File | Issue | Fix |
|------|-------|-----|
| `tiktok_auth.py` | BOM byte (U+FEFF) caused SyntaxError | Stripped — file now parses clean |
| `clipfarmer_run.py` | Upload endpoint was `/post/publish/video/init/` (requires video.publish scope) | Changed to `/post/publish/inbox/video/init/` (video.upload scope) |

## ⚠️ ACTION REQUIRED — Install missing packages
Run this in PowerShell from `C:\clipfarmer\`:
```
.\install_deps.ps1
```
Or manually:
```
pip install yt-dlp openai-whisper crewai crewai-tools litellm google-auth-oauthlib google-api-python-client customtkinter keyboard python-dotenv
```

### Packages needed per module:
| Module | Missing Package |
|--------|----------------|
| `downloader.py`, `scheduler.py` | `yt-dlp` |
| `processor.py` | `openai-whisper` |
| `youtube_uploader.py` | `google-auth-oauthlib`, `google-api-python-client` |
| `crewai_gemini.py`, `ai_crew.py` | `crewai`, `crewai-tools` |
| `dashboard.py` (desktop GUI) | `customtkinter`, `keyboard` |

## 🟡 CLEANUP RECOMMENDED
| Item | Action |
|------|--------|
| `instagram_uploader (1).py` | Duplicate of `instagram_uploader.py` — safe to delete |
| `C:\clipfarmer\*.py` (root copies) | These are stale copies of `clipfarmer\*.py` — can delete root-level duplicates |

## ✅ CONFIRMED OK
| Item | Status |
|------|--------|
| `config.json` (both locations) | Valid JSON ✅ |
| `hooks.json` (both locations) | Valid JSON ✅ |
| `C:\clipfarmer\storage\review_demo.mp4` | Exists (81.8 MB) ✅ |
| `C:\clipfarmer\logs\` | Exists with 40+ log files ✅ |
| `utils.py`, `setup.py` | No issues ✅ |
| All "MISSING PATH" warnings in scanner | False positives — paths exist on Windows ✅ |
