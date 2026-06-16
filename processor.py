"""
processor.py — ClipFarmer Phase 1
Crops video to 9:16, applies fingerprint disruption (micro-rotation + zoom + speed),
burns Whisper captions in cyberpunk orange, overlays background music,
adds 2-second Gen Z pattern interrupt hook, and 3-second CTA overlay.
Hard ceiling: 58 seconds max output duration for Shorts compliance.
"""

import os
import json
import logging
import random
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import whisper

from utils import load_config, update_job, get_video_info_ffprobe, format_srt_time

logger = logging.getLogger("clipfarmer.processor")

MAX_DURATION = 58.0

GENZ_HOOKS = {
    "motivational": ["unreal aura", "let him cook", "no cap fr", "built different", "main character"],
    "satisfying":   ["cured my anxiety", "lowkey healing", "so satisfying fr", "brain reset", "oddly okay"],
    "animals":      ["the audacity", "feral behavior", "unhinged fr", "not the vibe", "chaotic good"],
    "facts":        ["bro what", "actually wild", "lowkey cursed", "they hid this", "fr tho"],
    "hacks":        ["why didnt i know", "game changer fr", "no way this works", "actually goated", "life unlocked"],
    "default":      ["wait for it", "no cap", "lowkey unreal", "fr fr", "actually insane"],
}

HOOKS_FILE = Path("C:/clipfarmer/hooks.json")


class ClipProcessor:
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.processed_dir = Path(self.config["paths"]["processed"])
        self.music_dir = Path(self.config["paths"]["music"])
        self.temp_dir = Path(self.config["paths"]["captions_temp"])
        self.ffmpeg = self.config["paths"]["ffmpeg"]
        self.ffprobe = self.config["paths"]["ffprobe"]

        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        self.out_w = self.config["video"]["output_width"]
        self.out_h = self.config["video"]["output_height"]
        self.fps = self.config["video"]["target_fps"]
        self.crf = self.config["video"]["crf"]
        self.preset = self.config["video"]["preset"]

        self.music_vol = self.config["audio"]["music_volume"]
        self.voice_vol = self.config["audio"]["voice_volume"]

        self.cap_cfg = self.config["captions"]
        self._whisper_model = None

    @property
    def whisper_model(self):
        if self._whisper_model is None:
            model_name = self.cap_cfg["whisper_model"]
            logger.info(f"Loading Whisper model: {model_name}")
            self._whisper_model = whisper.load_model(model_name)
            logger.info("Whisper model loaded")
        return self._whisper_model

    # ── Step 1: Smart crop to 9:16 ────────────────────────────────────────────

    def _get_crop_filter(self, src_w: int, src_h: int) -> str:
        target_ratio = 9 / 16
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            crop_w = int(src_h * target_ratio)
            crop_h = src_h
            x = (src_w - crop_w) // 2
            y = 0
        else:
            crop_w = src_w
            crop_h = int(src_w / target_ratio)
            x = 0
            y = int((src_h - crop_h) * 0.40)

        return f"crop={crop_w}:{crop_h}:{x}:{y},scale={self.out_w}:{self.out_h}"

    # ── Step 2: Whisper transcription ─────────────────────────────────────────

    def transcribe(self, video_path: str, job_id: str,
                   max_duration: float = MAX_DURATION) -> Optional[str]:
        if not self.cap_cfg["enabled"]:
            return None

        logger.info(f"[{job_id[:8]}] Transcribing with Whisper (cap: {max_duration:.1f}s)...")
        srt_path = self.temp_dir / f"{job_id}.srt"

        try:
            result = self.whisper_model.transcribe(
                video_path,
                language=None,
                word_timestamps=True,
                verbose=False,
            )

            if result.get("segments"):
                result["segments"] = [
                    s for s in result["segments"]
                    if s["start"] < max_duration
                ]
                for seg in result["segments"]:
                    seg["end"] = min(seg["end"], max_duration)

            srt_content = self._whisper_to_srt(result)
            srt_path.write_text(srt_content, encoding="utf-8")
            logger.info(f"[{job_id[:8]}] Transcription done: {srt_path}")
            return str(srt_path)

        except Exception as e:
            logger.error(f"[{job_id[:8]}] Transcription failed: {e}")
            return None

    def _whisper_to_srt(self, result: dict) -> str:
        max_words = self.cap_cfg["max_words_per_line"]
        lines = []
        idx = 1

        if self.cap_cfg["style"] == "word_by_word":
            all_words = []
            for seg in result.get("segments", []):
                words = seg.get("words", [])
                if words:
                    all_words.extend(words)
                else:
                    text = seg["text"].strip()
                    words_in_seg = text.split()
                    dur = (seg["end"] - seg["start"]) / max(len(words_in_seg), 1)
                    for i, w in enumerate(words_in_seg):
                        all_words.append({
                            "word": w,
                            "start": seg["start"] + i * dur,
                            "end": seg["start"] + (i + 1) * dur,
                        })

            for i in range(0, len(all_words), max_words):
                chunk = all_words[i:i + max_words]
                if not chunk:
                    continue
                start = chunk[0]["start"]
                end = chunk[-1]["end"]
                text = " ".join(w["word"].strip() for w in chunk)
                lines.append(
                    f"{idx}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{text}\n"
                )
                idx += 1
        else:
            for seg in result.get("segments", []):
                text = seg["text"].strip()
                if not text:
                    continue
                lines.append(
                    f"{idx}\n{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n{text}\n"
                )
                idx += 1

        return "\n".join(lines)

    # ── Step 3: Cyberpunk orange subtitle style ────────────────────────────────

    def _subtitle_filter(self, srt_path: str) -> str:
        escaped = srt_path.replace("\\", "/").replace(":", "\\:")
        force_style = (
            "FontName=Impact,"
            "FontSize=52,"
            "PrimaryColour=&H000066FF&,"
            "OutlineColour=&H00000000&,"
            "BackColour=&H00000000&,"
            "Outline=4,"
            "Shadow=0,"
            "Bold=1,"
            "Alignment=2,"
            f"MarginV={int(self.out_h * (1 - self.cap_cfg['position_y_ratio']))}"
        )
        return f"subtitles='{escaped}':force_style='{force_style}'"

    # ── Step 4: Digital fingerprint disruption ────────────────────────────────

    def _fingerprint_filter(self) -> str:
        rotate = "rotate=0.01745:fillcolor=black"
        zoom_crop = f"scale={int(self.out_w * 1.03)}:{int(self.out_h * 1.03)},crop={self.out_w}:{self.out_h}"
        speed = "setpts=PTS/1.03"
        return f"{rotate},{zoom_crop},{speed}"

    # ── Step 5: Brain-weighted hook selection ─────────────────────────────────

    def _pick_weighted_hook(self, niche: str = "default") -> str:
        """Load hooks.json and select hook using brain-optimized weights. Falls back to flat random."""
        try:
            if HOOKS_FILE.exists():
                with open(HOOKS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                niche_hooks = (
                    data.get("niches", {})
                    .get(niche, data.get("niches", {}).get("default", {}))
                    .get("hooks", [])
                )
                if niche_hooks:
                    texts = [h["text"] for h in niche_hooks]
                    weights = [h.get("weight", 1.0) for h in niche_hooks]
                    return random.choices(texts, weights=weights, k=1)[0]
        except Exception:
            pass
        return random.choice(GENZ_HOOKS.get(niche, GENZ_HOOKS["default"]))

    def _hook_filter(self, niche: str = "default") -> str:
        hook_word = self._pick_weighted_hook(niche)
        return (
            f"drawtext=text='{hook_word}':"
            f"font=Impact:fontsize=58:"
            f"fontcolor=#FF6600:borderw=4:bordercolor=black:"
            f"x=(w-text_w)/2:y=h*0.18:"
            f"enable='between(t,0,2)'"
        )

    # ── Step 6: 3-second CTA overlay ──────────────────────────────────────────

    def _cta_filter(self, output_duration: float) -> str:
        cta_start = max(0, output_duration - 3)
        line1 = (
            f"drawtext=text='follow for more':"
            f"font=Impact:fontsize=44:"
            f"fontcolor=#FF6600:borderw=4:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-150:"
            f"enable='gte(t,{cta_start:.2f})'"
        )
        line2 = (
            f"drawtext=text='link in bio':"
            f"font=Impact:fontsize=44:"
            f"fontcolor=#FF6600:borderw=4:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-90:"
            f"enable='gte(t,{cta_start:.2f})'"
        )
        return f"{line1},{line2}"

    # ── Step 7: Pick random background music ──────────────────────────────────

    def _pick_music(self) -> Optional[str]:
        if not self.music_dir.exists():
            logger.warning(f"Music dir not found: {self.music_dir}")
            return None

        music_files = (
            list(self.music_dir.glob("*.mp3")) +
            list(self.music_dir.glob("*.wav")) +
            list(self.music_dir.glob("*.m4a")) +
            list(self.music_dir.glob("*.ogg"))
        )

        if not music_files:
            logger.warning("No music files found in music/")
            return None

        chosen = random.choice(music_files)
        logger.info(f"Music: {chosen.name}")
        return str(chosen)

    # ── Step 8: Full FFmpeg processing pipeline ────────────────────────────────

    def process(self, input_path: str, job_id: str,
                srt_path: Optional[str] = None,
                music_path: Optional[str] = None,
                niche: str = "default") -> Optional[str]:

        input_path = Path(input_path)
        output_path = self.processed_dir / f"{job_id}_final.mp4"

        info = get_video_info_ffprobe(str(input_path), self.ffprobe)
        if not info:
            logger.error(f"[{job_id[:8]}] Could not get video info")
            return None

        src_w = info["width"]
        src_h = info["height"]
        has_audio = info["has_audio"]
        raw_dur = info["duration"]

        clamped_input_dur = min(raw_dur, MAX_DURATION)
        output_duration = clamped_input_dur / 1.03

        if raw_dur > MAX_DURATION:
            logger.info(
                f"[{job_id[:8]}] Source is {raw_dur:.1f}s — clamping to {MAX_DURATION}s "
                f"-> output will be {output_duration:.1f}s"
            )
        else:
            logger.info(
                f"[{job_id[:8]}] Source is {raw_dur:.1f}s — within limit "
                f"-> output will be {output_duration:.1f}s"
            )

        logger.info(
            f"[{job_id[:8]}] Processing: {src_w}x{src_h} -> "
            f"{self.out_w}x{self.out_h} | {output_duration:.1f}s output"
        )

        crop_filter = self._get_crop_filter(src_w, src_h)
        music = music_path or self._pick_music()
        use_music = music is not None
        use_captions = srt_path is not None and self.cap_cfg["enabled"]

        inputs = ["-i", str(input_path)]
        if use_music:
            inputs += ["-i", music]

        vf = crop_filter
        vf += f",fps={self.fps}"
        vf += "," + self._fingerprint_filter()
        if use_captions:
            vf += "," + self._subtitle_filter(srt_path)
        vf += "," + self._hook_filter(niche)
        vf += "," + self._cta_filter(output_duration)

        audio_speed_filter = "atempo=1.03"

        if use_music and has_audio:
            filter_complex = (
                f"[0:v]{vf}[vout];"
                f"[1:a]volume={self.music_vol},aloop=loop=-1:size=2e+09[aout]"
            )
            map_args = ["-map", "[vout]", "-map", "[aout]"]
        elif use_music and not has_audio:
            filter_complex = (
                f"[0:v]{vf}[vout];"
                f"[1:a]volume={self.music_vol},aloop=loop=-1:size=2e+09[aout]"
            )
            map_args = ["-map", "[vout]", "-map", "[aout]"]
        elif has_audio:
            filter_complex = (
                f"[0:v]{vf}[vout];"
                f"[0:a]volume={self.voice_vol},{audio_speed_filter}[aout]"
            )
            map_args = ["-map", "[vout]", "-map", "[aout]"]
        else:
            filter_complex = f"[0:v]{vf}[vout]"
            map_args = ["-map", "[vout]"]

        cmd = [
            self.ffmpeg,
            "-y",
            "-t", str(clamped_input_dur),
            *inputs,
            "-filter_complex", filter_complex,
            *map_args,
            "-c:v", "libx264",
            "-crf", str(self.crf),
            "-preset", self.preset,
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            "-t", str(output_duration),
            str(output_path),
        ]

        logger.info(f"[{job_id[:8]}] Running FFmpeg...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600
            )

            if result.returncode != 0:
                logger.error(f"[{job_id[:8]}] FFmpeg error:\n{result.stderr[-2000:]}")
                update_job(job_id, {
                    "process_status": "error",
                    "error": result.stderr[-500:]
                }, self.config["paths"]["jobs_db"])
                return None

            logger.info(f"[{job_id[:8]}] Processed: {output_path} ({output_duration:.1f}s)")
            update_job(job_id, {
                "processed_path": str(output_path),
                "process_status": "complete",
                "processed_at": datetime.utcnow().isoformat(),
                "output_duration": round(output_duration, 1),
            }, self.config["paths"]["jobs_db"])

            return str(output_path)

        except subprocess.TimeoutExpired:
            logger.error(f"[{job_id[:8]}] FFmpeg timed out")
            update_job(job_id, {"process_status": "error", "error": "FFmpeg timeout"},
                       self.config["paths"]["jobs_db"])
            return None

        except Exception as e:
            logger.error(f"[{job_id[:8]}] Processing error: {e}")
            update_job(job_id, {"process_status": "error", "error": str(e)},
                       self.config["paths"]["jobs_db"])
            return None

    # ── High-level: full chain ─────────────────────────────────────────────────

    def process_full(self, video_path: str, job_id: str,
                     niche: str = "default") -> Optional[str]:
        srt_path = None
        if self.cap_cfg["enabled"]:
            srt_path = self.transcribe(video_path, job_id, max_duration=MAX_DURATION)
        return self.process(video_path, job_id, srt_path=srt_path, niche=niche)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    if len(sys.argv) < 3:
        print("Usage: python processor.py <video_path> <job_id> [niche]")
        sys.exit(1)

    niche = sys.argv[3] if len(sys.argv) > 3 else "default"
    proc = ClipProcessor()
    out = proc.process_full(sys.argv[1], sys.argv[2], niche=niche)
    print(f"\nOutput: {out}" if out else "\nFailed")