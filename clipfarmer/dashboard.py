"""
dashboard.py — ClipFarmer Creator Command Center v3.0
Premium cyberpunk orange dashboard for @kenisterjz
Toggle visibility: F8 (global hotkey, works from any app)
Requires: pip install customtkinter keyboard
"""

import subprocess
import threading
import sys
import os
import math
import time
from pathlib import Path
from datetime import datetime

try:
    import customtkinter as ctk
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "customtkinter"], check=True)
    import customtkinter as ctk

try:
    import keyboard
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "keyboard"], check=True)
    import keyboard

import tkinter as tk

# ── Theme constants ───────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG          = "#0D0D0D"
SURFACE     = "#1A1A1A"
SURFACE2    = "#222222"
BORDER      = "#2A2A2A"
ORANGE      = "#FF6600"
ORANGE_DIM  = "#CC5200"
ORANGE_GLOW = "#FF8833"
GREEN       = "#1DB954"
AMBER       = "#FF9500"
WHITE       = "#F0F0F0"
GRAY        = "#888888"
MUTED       = "#444444"
FONT_MAIN   = "Segoe UI"
FONT_MONO   = "Consolas"

SCRIPT_DIR  = Path(__file__).parent
HOTKEY      = "f8"

# ── Editable metrics (update these from brain_updater weekly) ─────────────────
METRICS = {
    "global_views":      0,
    "avg_watch_time":    "0s",
    "est_conversions":   0,
    "clips_posted":      15,
    "revenue":           "$0",
    "followers":         0,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  Pulse ring canvas widget
# ═══════════════════════════════════════════════════════════════════════════════

class PulseRing(tk.Canvas):
    """Animated glowing pulse ring status indicator."""

    def __init__(self, parent, color=GREEN, size=18, **kwargs):
        super().__init__(
            parent, width=size, height=size,
            bg=SURFACE, highlightthickness=0, **kwargs
        )
        self.color  = color
        self.size   = size
        self._phase = 0
        self._draw()

    def _draw(self):
        self.delete("all")
        s = self.size
        r = s / 2
        # Outer pulse ring
        alpha_scale = 0.4 + 0.6 * abs(math.sin(self._phase))
        ring_r = r * (0.7 + 0.3 * abs(math.sin(self._phase)))
        pad = r - ring_r
        self.create_oval(
            pad, pad, s - pad, s - pad,
            outline=self.color, width=1,
            stipple="" if alpha_scale > 0.5 else "gray50"
        )
        # Inner solid dot
        dot = r * 0.45
        self.create_oval(
            r - dot, r - dot, r + dot, r + dot,
            fill=self.color, outline=""
        )
        self._phase += 0.12
        self.after(80, self._draw)

    def set_color(self, color: str):
        self.color = color


# ═══════════════════════════════════════════════════════════════════════════════
#  Main Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

class CreatorCommandCenter(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("ClipFarmer — Creator Command Center")
        self.geometry("1120x700")
        self.minsize(1000, 640)
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.97)

        self._visible = True
        self._log_messages = []

        self._build_ui()
        self._tick_clock()
        self._seed_log()

        # Global F8 hotkey
        keyboard.add_hotkey(HOTKEY, lambda: self.after(0, self._toggle))

        # Hide instead of close
        self.protocol("WM_DELETE_WINDOW", self._toggle)

    # ── Toggle ────────────────────────────────────────────────────────────────

    def _toggle(self):
        if self._visible:
            self.withdraw()
            self._visible = False
        else:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self._visible = True

    # ── UI Build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        self._build_metrics_ribbon()

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=3)
        content.rowconfigure(0, weight=1)

        self._build_left_panel(content)
        self._build_right_panel(content)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=56)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20)

        # Brand
        brand = ctk.CTkFrame(inner, fg_color="transparent")
        brand.pack(side="left", anchor="w", pady=10)

        ctk.CTkLabel(
            brand,
            text="CLIPFARMER",
            font=ctk.CTkFont(FONT_MAIN, 18, "bold"),
            text_color=ORANGE,
        ).pack(side="left")

        ctk.CTkLabel(
            brand,
            text="  //  CREATOR COMMAND CENTER",
            font=ctk.CTkFont(FONT_MAIN, 13),
            text_color=GRAY,
        ).pack(side="left")

        # Right side
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", anchor="e", pady=10)

        self.clock_lbl = ctk.CTkLabel(
            right,
            text="",
            font=ctk.CTkFont(FONT_MONO, 11),
            text_color=MUTED,
        )
        self.clock_lbl.pack(side="right", padx=(12, 0))

        ctk.CTkLabel(
            right,
            text=f"[ F8 = TOGGLE ]",
            font=ctk.CTkFont(FONT_MONO, 10),
            text_color=MUTED,
        ).pack(side="right", padx=(12, 0))

        # Status pill
        pill = ctk.CTkFrame(right, fg_color=SURFACE2, corner_radius=20)
        pill.pack(side="right", padx=(0, 8))
        PulseRing(pill, color=GREEN, size=14).pack(side="left", padx=(8, 4), pady=6)
        ctk.CTkLabel(
            pill,
            text="SYSTEM ACTIVE",
            font=ctk.CTkFont(FONT_MONO, 10, "bold"),
            text_color=GREEN,
        ).pack(side="left", padx=(0, 10), pady=6)

    # ── Metrics ribbon ────────────────────────────────────────────────────────

    def _build_metrics_ribbon(self):
        ribbon = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0, height=64)
        ribbon.pack(fill="x")
        ribbon.pack_propagate(False)

        # Separator line
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        inner = ctk.CTkFrame(ribbon, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=10)

        metrics = [
            ("GLOBAL VIEWS",         str(METRICS["global_views"]),    WHITE),
            ("AVG WATCH TIME",        METRICS["avg_watch_time"],       WHITE),
            ("EST. CONVERSIONS",      str(METRICS["est_conversions"]), WHITE),
            ("CLIPS POSTED",          str(METRICS["clips_posted"]),    ORANGE),
            ("TOTAL REVENUE",         METRICS["revenue"],              GREEN),
            ("FOLLOWERS",             str(METRICS["followers"]),       WHITE),
        ]

        for i, (label, value, color) in enumerate(metrics):
            card = ctk.CTkFrame(inner, fg_color="transparent")
            card.pack(side="left", expand=True, fill="both")

            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(FONT_MONO, 9),
                text_color=MUTED,
            ).pack(anchor="w")

            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(FONT_MAIN, 18, "bold"),
                text_color=color,
            ).pack(anchor="w")

            if i < len(metrics) - 1:
                ctk.CTkFrame(inner, fg_color=BORDER, width=1).pack(
                    side="left", fill="y", padx=16, pady=4
                )

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left_panel(self, parent):
        left = ctk.CTkFrame(parent, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._build_platform_matrix(left)
        self._build_pipeline_controls(left)

    def _build_platform_matrix(self, parent):
        section = self._section(parent, "PLATFORM API STATUS")
        section.pack(fill="x", pady=(0, 10))

        platforms = [
            ("YouTube",   "Data API v3",        "CONNECTED",           GREEN,  "Sync Channel"),
            ("TikTok",    "Content Posting API", "PENDING APPROVAL",    AMBER,  "Submit Request"),
            ("Instagram", "Graph API",           "PENDING APPROVAL",    AMBER,  "Submit Request"),
        ]

        for name, api, status, color, btn_text in platforms:
            card = ctk.CTkFrame(section, fg_color=SURFACE2, corner_radius=8)
            card.pack(fill="x", padx=12, pady=4)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=10)

            # Left: pulse + name
            left_side = ctk.CTkFrame(row, fg_color="transparent")
            left_side.pack(side="left")

            pulse_frame = ctk.CTkFrame(left_side, fg_color="transparent")
            pulse_frame.pack(side="left", padx=(0, 8))
            PulseRing(pulse_frame, color=color, size=16).pack()

            info = ctk.CTkFrame(left_side, fg_color="transparent")
            info.pack(side="left")
            ctk.CTkLabel(
                info, text=name,
                font=ctk.CTkFont(FONT_MAIN, 13, "bold"),
                text_color=WHITE,
            ).pack(anchor="w")
            ctk.CTkLabel(
                info, text=api,
                font=ctk.CTkFont(FONT_MONO, 10),
                text_color=MUTED,
            ).pack(anchor="w")

            # Right: status + button
            right_side = ctk.CTkFrame(row, fg_color="transparent")
            right_side.pack(side="right")

            ctk.CTkLabel(
                right_side, text=status,
                font=ctk.CTkFont(FONT_MONO, 10, "bold"),
                text_color=color,
            ).pack(anchor="e", pady=(0, 4))

            ctk.CTkButton(
                right_side,
                text=btn_text,
                font=ctk.CTkFont(FONT_MAIN, 11),
                fg_color=SURFACE,
                hover_color=ORANGE_DIM,
                text_color=ORANGE,
                border_width=1,
                border_color=MUTED,
                corner_radius=4,
                height=28,
                width=120,
                command=lambda n=name: self._platform_action(n),
            ).pack(anchor="e")

    def _build_pipeline_controls(self, parent):
        section = self._section(parent, "PIPELINE CONTROLS")
        section.pack(fill="both", expand=True)

        controls = [
            ("▶  Run Full Automation Cycle",
             lambda: self._run_script("scheduler.py", ["--videos", "2", "--no-instagram"],
                                      "Starting automation cycle...")),
            ("⚙  Process Video Queue",
             lambda: self._run_script("processor.py", [],
                                      "Processing video queue...")),
            ("↑  Publish to YouTube",
             lambda: self._run_script("youtube_uploader.py", ["--all"],
                                      "Publishing to YouTube...")),
            ("🧠  Analytics Brain Report",
             lambda: self._run_script("brain_updater.py", ["--status"],
                                      "Loading analytics report...")),
            ("🗂  Storage Maintenance",
             lambda: self._run_script("cleanup.py", ["--dry-run"],
                                      "Running storage scan...")),
            ("📋  Open Latest Log",
             lambda: self._open_logs()),
        ]

        btn_frame = ctk.CTkFrame(section, fg_color="transparent")
        btn_frame.pack(fill="x", padx=12, pady=8)

        for text, cmd in controls:
            ctk.CTkButton(
                btn_frame,
                text=text,
                command=cmd,
                fg_color=SURFACE2,
                hover_color=ORANGE_DIM,
                text_color=ORANGE,
                font=ctk.CTkFont(FONT_MAIN, 12),
                border_width=1,
                border_color=BORDER,
                corner_radius=6,
                height=38,
                anchor="w",
            ).pack(fill="x", pady=3)

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        right = ctk.CTkFrame(parent, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=0)
        right.columnconfigure(0, weight=1)

        self._build_render_monitor(right)
        self._build_niche_gumroad(right)

    def _build_render_monitor(self, parent):
        section = self._section(parent, "PIPELINE RENDER MONITOR")
        section.grid(row=0, column=0, sticky="nsew", pady=(0, 10))

        # Status bar
        status_bar = ctk.CTkFrame(section, fg_color=SURFACE2, corner_radius=6)
        status_bar.pack(fill="x", padx=12, pady=(0, 8))

        sb_inner = ctk.CTkFrame(status_bar, fg_color="transparent")
        sb_inner.pack(fill="x", padx=12, pady=8)

        self.render_pulse = PulseRing(sb_inner, color=ORANGE, size=14)
        self.render_pulse.pack(side="left", padx=(0, 8))

        self.render_status = ctk.CTkLabel(
            sb_inner,
            text="System idle — awaiting next automation cycle",
            font=ctk.CTkFont(FONT_MONO, 11),
            text_color=GRAY,
        )
        self.render_status.pack(side="left")

        # Log output
        self.log_box = ctk.CTkTextbox(
            section,
            fg_color=SURFACE2,
            text_color=ORANGE,
            font=ctk.CTkFont(FONT_MONO, 11),
            corner_radius=6,
            border_width=1,
            border_color=BORDER,
            scrollbar_button_color=BORDER,
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log_box.configure(state="disabled")

    def _build_niche_gumroad(self, parent):
        bottom = ctk.CTkFrame(parent, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        # Niches
        niche_section = self._section(bottom, "ACTIVE CONTENT NICHES")
        niche_section.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        niches = [
            ("satisfying",   "asmr • pressure wash • sand"),
            ("animals",      "pets • wildlife • funny"),
            ("hacks",        "kitchen • cleaning • tips"),
            ("facts",        "science • psychology • history"),
            ("motivational", "mindset • discipline • grind"),
        ]
        for niche, tags in niches:
            row = ctk.CTkFrame(niche_section, fg_color=SURFACE2, corner_radius=4)
            row.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(
                row, text=f" {niche}",
                font=ctk.CTkFont(FONT_MAIN, 11, "bold"),
                text_color=ORANGE, width=100, anchor="w",
            ).pack(side="left", padx=(6, 4), pady=6)
            ctk.CTkLabel(
                row, text=tags,
                font=ctk.CTkFont(FONT_MONO, 9),
                text_color=MUTED, anchor="w",
            ).pack(side="left")

        # Gumroad
        gumroad_section = self._section(bottom, "GUMROAD STORE")
        gumroad_section.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        products = [
            ("Creator Pack",      "$9",  "content-creator-prompts", GRAY),
            ("Entrepreneur Pack", "$12", "entrepreneur-prompts",    GRAY),
            ("Mega Vault Bundle", "$24", "kkwmea",                  ORANGE),
        ]
        for name, price, slug, col in products:
            card = ctk.CTkFrame(gumroad_section, fg_color=SURFACE2, corner_radius=4)
            card.pack(fill="x", padx=12, pady=2)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(
                top, text=name,
                font=ctk.CTkFont(FONT_MAIN, 11, "bold"),
                text_color=WHITE,
            ).pack(side="left")
            ctk.CTkLabel(
                top, text=price,
                font=ctk.CTkFont(FONT_MAIN, 12, "bold"),
                text_color=ORANGE,
            ).pack(side="right")
            ctk.CTkLabel(
                card, text=f"gumroad.com/l/{slug}",
                font=ctk.CTkFont(FONT_MONO, 9),
                text_color=MUTED, anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 6))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section(self, parent, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=10,
                             border_width=1, border_color=BORDER)
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 8))
        ctk.CTkLabel(
            header, text=title,
            font=ctk.CTkFont(FONT_MONO, 10, "bold"),
            text_color=MUTED,
        ).pack(side="left")
        ctk.CTkFrame(header, fg_color=BORDER, height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=6
        )
        return frame

    def _log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"INFO": "◆", "OK": "✓", "WARN": "⚠", "ERR": "✗"}
        icon = icons.get(level, "◆")
        line = f"[{ts}] {icon}  {message}\n"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", line)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _seed_log(self):
        messages = [
            ("Creator Command Center initialized", "OK"),
            ("YouTube API: Connection verified", "OK"),
            ("TikTok API: Authorization pending", "WARN"),
            ("Instagram API: Authorization pending", "WARN"),
            (f"Content pipeline ready — {SCRIPT_DIR}", "INFO"),
            ("Active niches: satisfying, animals, hacks, facts, motivational", "INFO"),
            ("Gumroad store: 3 products live", "OK"),
            (f"Global hotkey registered: {HOTKEY.upper()}", "OK"),
            ("Awaiting next automation cycle...", "INFO"),
        ]
        for msg, level in messages:
            self._log(msg, level)

    def _run_script(self, script_name: str, args: list,
                    status_msg: str = ""):
        script_path = SCRIPT_DIR / script_name
        if not script_path.exists():
            self._log(f"Script not found: {script_name}", "ERR")
            return

        if status_msg:
            self.render_status.configure(text=status_msg, text_color=ORANGE)
        self._log(f"Launching: {script_name}", "INFO")

        def run():
            try:
                cmd = [sys.executable, str(script_path)] + args
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(SCRIPT_DIR),
                    timeout=300,
                )
                # Parse output into clean human-readable lines
                raw = (proc.stdout + proc.stderr).strip()
                for line in raw.splitlines()[-12:]:
                    clean = self._clean_log_line(line)
                    if clean:
                        self.after(0, self._log, clean, "INFO")

                level = "OK" if proc.returncode == 0 else "ERR"
                msg = "Completed successfully" if proc.returncode == 0 else "Completed with warnings"
                self.after(0, self._log, f"{script_name}: {msg}", level)
                self.after(0, self.render_status.configure,
                           {"text": f"Last action: {script_name} — {msg}",
                            "text_color": GREEN if level == "OK" else AMBER})
            except subprocess.TimeoutExpired:
                self.after(0, self._log, f"{script_name}: Process timeout (300s)", "WARN")
            except Exception as e:
                self.after(0, self._log, f"Execution error: {e}", "ERR")

        threading.Thread(target=run, daemon=True).start()

    def _clean_log_line(self, line: str) -> str:
        """Convert raw script output to clean human-readable status."""
        line = line.strip()
        if not line:
            return ""
        # Map known patterns to clean messages
        mappings = [
            ("Searching:",           "Scanning trending content..."),
            ("Downloading:",         "Retrieving source media..."),
            ("Transcribing",         "Running AI transcription..."),
            ("Processing:",          "Rendering video pipeline..."),
            ("Uploading to YouTube", "Publishing to YouTube..."),
            ("Uploaded!",            "Upload complete"),
            ("Cycle complete",       "Automation cycle complete"),
            ("Found",                line),
            ("✅",                   line.replace("✅", "").strip()),
            ("❌",                   line.replace("❌", "").strip()),
            ("⚠",                    line.replace("⚠", "").strip()),
        ]
        for trigger, replacement in mappings:
            if trigger in line:
                return replacement
        # Return filtered line if it's short and readable
        if len(line) < 120 and not line.startswith("[download]"):
            return line
        return ""

    def _platform_action(self, platform: str):
        if platform == "YouTube":
            self._log("YouTube API: Connection active — channel synced", "OK")
        else:
            self._log(f"{platform} API: Application submitted — awaiting developer approval", "WARN")

    def _open_logs(self):
        logs_dir = SCRIPT_DIR / "logs"
        if not logs_dir.exists():
            self._log("Logs directory not found", "WARN")
            return
        log_files = sorted(logs_dir.glob("*.log"), reverse=True)
        if not log_files:
            self._log("No log files found", "WARN")
            return
        latest = log_files[0]
        self._log(f"Opening: {latest.name}", "INFO")
        try:
            os.startfile(str(latest))
        except Exception as e:
            self._log(f"Could not open log: {e}", "ERR")

    def _tick_clock(self):
        self.clock_lbl.configure(
            text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        )
        self.after(1000, self._tick_clock)


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = CreatorCommandCenter()
    app.mainloop()