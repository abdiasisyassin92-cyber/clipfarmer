# ClipFarmer — Phase 1: Download & Process Pipeline

Automated viral clip farming system. Download → Crop 9:16 → Whisper Captions → Music → Ready to post.

---

## 📁 Structure

```
clipfarmer/
├── config.json          # All settings (paths, quality, captions)
├── downloader.py        # yt-dlp wrapper
├── processor.py         # FFmpeg crop + Whisper captions + music
├── pipeline.py          # Orchestrator (run this)
├── utils.py             # Shared helpers
├── setup.py             # First-run environment check
├── dashboard.html       # Jarvis local dashboard
├── requirements.txt
├── downloads/           # Raw downloaded videos (auto-created)
├── processed/           # Final 9:16 clips (auto-created)
├── music/               # Drop your background music here
├── logs/                # Pipeline logs (auto-created)
└── temp/captions/       # Whisper SRT files (auto-created)
```

---

## 🚀 First-Time Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

> **Whisper note**: First run downloads the model (~140MB for `base`). 
> Faster CPU? Use `"whisper_model": "tiny"` in config.json.
> Have a GPU? Use `"whisper_model": "small"` or `"medium"` for better accuracy.

### 2. Verify your environment
```bash
cd clipfarmer
python setup.py
```

### 3. Add background music
Drop royalty-free `.mp3` or `.wav` files into `./music/`.
Free sources:
- https://pixabay.com/music/
- https://freemusicarchive.org

---

## ⚙️ Configuration (config.json)

Key settings to check:

```json
"paths": {
  "ffmpeg": "C:\\ffmpeg\\bin\\ffmpeg.exe",   ← your ffmpeg path
  "ffprobe": "C:\\ffmpeg\\bin\\ffprobe.exe"  ← your ffprobe path
}

"captions": {
  "whisper_model": "base",   ← tiny/base/small/medium/large
  "style": "word_by_word",   ← word_by_word or segment
  "max_words_per_line": 4    ← words per caption block
}

"download": {
  "max_duration_seconds": 180   ← skip videos longer than this
}
```

---

## 📋 Usage

### Single video
```bash
python pipeline.py --url https://youtube.com/watch?v=XXXXX
```

### Batch from file
```bash
# Edit urls_sample.txt with your URLs (one per line)
python pipeline.py --file urls_sample.txt
```

### Check job status
```bash
python pipeline.py --status
```

### Dashboard
```bash
# Open dashboard.html in browser, then:
python -m http.server 8080
# Visit: http://localhost:8080/dashboard.html
```

---

## 🎬 What Phase 1 Does

1. **Download** — yt-dlp pulls the video in best quality up to 1080p
2. **Crop** — Smart center-crop to 9:16 (1080×1920), face-biased vertical position
3. **Captions** — Whisper AI transcribes audio → word-by-word SRT burned in
4. **Music** — Random track from `./music/` mixed under voice at 15% volume
5. **Encode** — H.264 CRF 18 output, faststart flag for mobile streaming

---

## 🔜 Coming in Phase 2

- Auto-post to TikTok, Instagram Reels, YouTube Shorts
- Growth tracking dashboard with real follower/view data
- Scheduling queue (post on your work-off days: Tue/Thu/Sat/Sun)
- Thumbnail auto-generation
- Viral score predictor

---

## 🐛 Troubleshooting

**FFmpeg not found**: Check `config.json` paths match your `C:\ffmpeg\bin\ffmpeg.exe`

**Whisper slow**: Switch to `"whisper_model": "tiny"` in config.json. Still slow? Disable captions: `"enabled": false`

**Download fails**: Try `pip install -U yt-dlp` (updates frequently to fix site changes)

**No audio in output**: Check the source video has audio. Silent videos get music only.
