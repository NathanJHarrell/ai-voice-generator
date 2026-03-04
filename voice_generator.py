"""
AI Voice Generator
A desktop application for generating AI voice clips using edge-tts.
"""

import asyncio
import glob
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from datetime import datetime
from tkinter import filedialog
import tkinter as tk

import customtkinter as ctk
import edge_tts
import pygame


_APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_ffmpeg() -> str | None:
    """Locate the ffmpeg executable, searching common install paths on Windows."""
    # 1. Check if it's already on PATH
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 2. Check bundled ffmpeg in our own app directory
    local = os.path.join(_APP_DIR, "ffmpeg", "bin", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if os.path.isfile(local):
        return local

    if os.name != "nt":
        return None

    # 3. Known exact path pattern for WinGet-installed ffmpeg (Gyan.FFmpeg)
    #    WinGet installs to: %LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*\bin\ffmpeg.exe
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile = os.environ.get("USERPROFILE", "")
    programdata = os.environ.get("PROGRAMDATA", "")

    winget_pkgs = os.path.join(localappdata, "Microsoft", "WinGet", "Packages")
    print(f"[ffmpeg] Checking WinGet packages dir: {winget_pkgs} (exists: {os.path.isdir(winget_pkgs)})")
    if os.path.isdir(winget_pkgs):
        # Look for Gyan.FFmpeg package directories specifically
        try:
            entries = os.listdir(winget_pkgs)
            ffmpeg_entries = [e for e in entries if "ffmpeg" in e.lower()]
            print(f"[ffmpeg] WinGet ffmpeg packages found: {ffmpeg_entries}")
            for entry in ffmpeg_entries:
                pkg_dir = os.path.join(winget_pkgs, entry)
                if os.path.isdir(pkg_dir):
                    # Walk this package to find ffmpeg.exe in a bin/ folder
                    for dirpath, dirnames, filenames in os.walk(pkg_dir):
                        if "ffmpeg.exe" in filenames:
                            candidate = os.path.join(dirpath, "ffmpeg.exe")
                            print(f"[ffmpeg] Found candidate: {candidate}")
                            if "bin" in dirpath.lower():
                                return candidate
                            found = found or candidate
        except (PermissionError, OSError) as e:
            print(f"[ffmpeg] Error searching WinGet packages: {e}")
        if found:
            return found

    # 4. Direct checks for common install locations (fast)
    direct_checks = [
        os.path.join(localappdata, "Microsoft", "WinGet", "Links", "ffmpeg.exe"),
        os.path.join(userprofile, "scoop", "shims", "ffmpeg.exe"),
        os.path.join(programdata, "chocolatey", "bin", "ffmpeg.exe"),
        "C:\\ffmpeg\\bin\\ffmpeg.exe",
        "C:\\ffmpeg\\ffmpeg.exe",
        "C:\\tools\\ffmpeg\\bin\\ffmpeg.exe",
    ]
    for candidate in direct_checks:
        if os.path.isfile(candidate):
            return candidate

    # 5. Recursive search in Program Files as last resort
    for root in ("C:\\Program Files", "C:\\Program Files (x86)"):
        if not os.path.isdir(root):
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                if "ffmpeg.exe" in filenames:
                    return os.path.join(dirpath, "ffmpeg.exe")
        except (PermissionError, OSError):
            pass

    return None


def _download_ffmpeg() -> str | None:
    """Download a portable ffmpeg to the app directory (Windows only)."""
    if os.name != "nt":
        return None

    ffmpeg_dir = os.path.join(_APP_DIR, "ffmpeg", "bin")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    ffprobe_exe = os.path.join(ffmpeg_dir, "ffprobe.exe")

    if os.path.isfile(ffmpeg_exe):
        return ffmpeg_exe

    try:
        import io
        import urllib.request
        import zipfile

        # Use the essentials build — small (~80MB zip) and has everything needed
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        print(f"Downloading portable ffmpeg from {url} ...")
        print("(This is a one-time download, ~80 MB)")

        # Download
        with urllib.request.urlopen(url, timeout=120) as resp:
            data = resp.read()

        # Extract just ffmpeg.exe and ffprobe.exe from the zip
        os.makedirs(ffmpeg_dir, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.namelist():
                basename = os.path.basename(member)
                if basename in ("ffmpeg.exe", "ffprobe.exe"):
                    target = os.path.join(ffmpeg_dir, basename)
                    with zf.open(member) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)

        if os.path.isfile(ffmpeg_exe):
            print(f"ffmpeg installed to {ffmpeg_dir}")
            return ffmpeg_exe

    except Exception as e:
        print(f"Auto-download of ffmpeg failed: {e}")
        print("You can manually download ffmpeg from https://www.gyan.dev/ffmpeg/builds/")
        print(f"and place ffmpeg.exe in: {ffmpeg_dir}")

    return None


# Auto-detect ffmpeg and configure pydub to use it
_FFMPEG_PATH = _find_ffmpeg()

if _FFMPEG_PATH:
    print(f"[ffmpeg] Found at: {_FFMPEG_PATH}")
else:
    print("[ffmpeg] Not found on system, will attempt auto-download...")

# If not found, try downloading a portable copy
if _FFMPEG_PATH is None and os.name == "nt":
    _FFMPEG_PATH = _download_ffmpeg()

if _FFMPEG_PATH:
    # Set environment so pydub's import-time check finds ffmpeg
    _ffmpeg_bin_dir = os.path.dirname(_FFMPEG_PATH)
    if _ffmpeg_bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _ffmpeg_bin_dir + os.pathsep + os.environ.get("PATH", "")

import warnings
# Globally suppress pydub's RuntimeWarning about missing ffmpeg —
# we handle detection ourselves and the warning fires at import time
# before we can configure the path.
warnings.filterwarnings("ignore", message="Couldn't find ffmpeg", category=RuntimeWarning)
warnings.filterwarnings("ignore", message="Couldn't find ffprobe", category=RuntimeWarning)

try:
    from pydub import AudioSegment
    if _FFMPEG_PATH:
        # Point pydub at the discovered ffmpeg explicitly
        AudioSegment.converter = _FFMPEG_PATH
        _ffprobe = os.path.join(os.path.dirname(_FFMPEG_PATH), "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if os.path.isfile(_ffprobe):
            AudioSegment.ffprobe = _ffprobe
        print(f"[ffmpeg] pydub configured successfully")
    PYDUB_AVAILABLE = _FFMPEG_PATH is not None
except ImportError:
    PYDUB_AVAILABLE = False

if not PYDUB_AVAILABLE:
    print("[ffmpeg] WARNING: ffmpeg not available. Text Effects, WAV/OGG export, and long text chunking will be limited.")
    print(f"[ffmpeg] To fix: download ffmpeg from https://www.gyan.dev/ffmpeg/builds/")
    print(f"[ffmpeg] and place ffmpeg.exe in: {os.path.join(_APP_DIR, 'ffmpeg', 'bin')}")

# ── Text Effects ────────────────────────────────────────────────────────────
# Maps effect tag names to edge-tts parameter overrides
EFFECTS_MAP = {
    "whisper": {"volume": "-80%"},
    "soft":    {"volume": "-40%"},
    "loud":    {"volume": "+50%"},
    "slow":    {"rate": "-30%"},
    "fast":    {"rate": "+30%"},
    "high":    {"pitch": "+30Hz"},
    "low":     {"pitch": "-30Hz"},
}

# Regex: matches [pause], [long pause], or [effect]...[/effect]
_EFFECT_NAMES = "|".join(EFFECTS_MAP.keys())
EFFECTS_PATTERN = re.compile(
    rf'\[pause\]|\[long pause\]|\[({_EFFECT_NAMES})\](.*?)\[/\1\]',
    re.DOTALL,
)


# ── Presets File ──────────────────────────────────────────────────────────────
_PRESETS_FILE = os.path.join(_APP_DIR, "voice_presets.json")

# ── Long Text Chunking ───────────────────────────────────────────────────────
_MAX_CHUNK_CHARS = 2000  # edge-tts works best with moderate-length text


def _chunk_text(text: str, max_chars: int = _MAX_CHUNK_CHARS) -> list[str]:
    """Split long text into chunks at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    # Split by sentence-ending punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}" if current else sentence

    if current.strip():
        chunks.append(current.strip())

    # Safety: if any chunk is still too long, hard-split on spaces
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final.append(chunk)
        else:
            words = chunk.split()
            part = ""
            for word in words:
                if len(part) + len(word) + 1 > max_chars and part:
                    final.append(part.strip())
                    part = word
                else:
                    part = f"{part} {word}" if part else word
            if part.strip():
                final.append(part.strip())

    return final if final else [text]


# ── Appearance ───────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ── Main Application ─────────────────────────────────────────────────────────
class VoiceGeneratorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AI Voice Studio")
        self.geometry("1100x720")
        self.minsize(900, 700)
        self.configure(fg_color="#0D0E15")

        # State
        self.voices: list[dict] = []
        self.languages: list[str] = []
        self.filtered_voices: list[dict] = []
        self.current_audio_path: str | None = None
        self.is_playing = False
        self.is_generating = False
        self.history: list[dict] = []  # Recent generated clips
        self.batch_cancel = False  # Flag for cancelling batch generation

        # Init audio mixer
        pygame.mixer.init()

        # Build UI
        self._build_ui()

        # Fetch voices in background
        self._set_status("Loading voices...")
        threading.Thread(target=self._load_voices, daemon=True).start()

    # ── UI Construction ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Colors for the "glassy" dark modern theme
        # Use deep dark blue for window BG
        BG_COLOR = "#0D0E15"
        # We will use transparent colors with subtle borders instead of solid panel colors
        PANEL_BORDER = "#2B2D42"
        PANEL_TINT = "#181A25"
        ACCENT_COLOR = "#3B82F6" # vibrant blue similar to image
        ACCENT_HOVER = "#2563EB"
        INPUT_BG = "#0F111A" # slightly lighter than deep bg

        # Configure grid layout (1x2) - Sidebar and Main Content
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # --- Sidebar ---
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=PANEL_TINT)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1) # spacer

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="🎙 AI Voice Studio", font=ctk.CTkFont(size=20, weight="bold", family="Segoe UI"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))

        # Generate button needs a custom style similar to the image
        self.generate_btn = ctk.CTkButton(
            self.sidebar_frame, text="⚡ Generate", command=self._on_generate, 
            height=45, corner_radius=12, font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER
        )
        self.generate_btn.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        # Play/Stop row
        self.play_stop_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.play_stop_frame.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        self.play_stop_frame.grid_columnconfigure((0, 1), weight=1)

        self.play_btn = ctk.CTkButton(
            self.play_stop_frame, text="▶", command=self._on_play_pause, 
            height=40, corner_radius=12, state="disabled", font=ctk.CTkFont(size=20), 
            fg_color="transparent", hover_color="#1E2030", border_width=1, border_color=ACCENT_COLOR, text_color=ACCENT_COLOR
        )
        self.play_btn.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.stop_btn = ctk.CTkButton(
            self.play_stop_frame, text="⏹", command=self._on_stop, 
            height=40, corner_radius=12, state="disabled", font=ctk.CTkFont(size=20),
            fg_color="transparent", hover_color="#1E2030", border_width=1, border_color="#EF4444", text_color="#EF4444"
        )
        self.stop_btn.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # Tools
        btn_kwargs = {
            "fg_color": "transparent", "hover_color": "#1E2030", 
            "border_width": 1, "border_color": PANEL_BORDER,
            "corner_radius": 8, "text_color": "#E0E0E0", "height": 36
        }

        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="💾 Save As", command=self._on_save, state="disabled", **btn_kwargs)
        self.save_btn.grid(row=3, column=0, padx=20, pady=6, sticky="ew")

        self.history_btn = ctk.CTkButton(self.sidebar_frame, text="🕒 History", command=self._show_history_dialog, **btn_kwargs)
        self.history_btn.grid(row=4, column=0, padx=20, pady=6, sticky="ew")

        self.presets_btn = ctk.CTkButton(self.sidebar_frame, text="⭐ Presets", command=self._show_presets_dialog, **btn_kwargs)
        self.presets_btn.grid(row=5, column=0, padx=20, pady=6, sticky="ew")

        self.batch_btn = ctk.CTkButton(self.sidebar_frame, text="📑 Batch", command=self._show_batch_dialog, **btn_kwargs)
        self.batch_btn.grid(row=6, column=0, padx=20, pady=6, sticky="ew")

        self.srt_btn = ctk.CTkButton(self.sidebar_frame, text="📝 Export SRT", command=self._on_export_srt, state="disabled", **btn_kwargs)
        self.srt_btn.grid(row=7, column=0, padx=20, pady=6, sticky="ew")

        # Status at bottom of sidebar
        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="Ready", font=ctk.CTkFont(size=12), text_color="#A0A0A0", wraplength=160)
        self.status_label.grid(row=10, column=0, padx=20, pady=(10, 20), sticky="s")


        # --- Main Frame ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1) # text input expands

        # Top Section: Options Panel
        self.options_frame = ctk.CTkFrame(self.main_frame, fg_color=PANEL_TINT, corner_radius=15, border_width=1, border_color=PANEL_BORDER)
        self.options_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        self.options_frame.grid_columnconfigure((0,1,2), weight=1)

        menu_kwargs = {
            "fg_color": INPUT_BG, "button_color": INPUT_BG, 
            "button_hover_color": "#1E2030", "dropdown_fg_color": INPUT_BG,
            "corner_radius": 8
        }

        # Language
        lang_frame = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        lang_frame.grid(row=0, column=0, padx=20, pady=15, sticky="ew")
        ctk.CTkLabel(lang_frame, text="🌐 Language", font=ctk.CTkFont(size=13, weight="bold"), text_color="#D0D0D0").pack(anchor="w", pady=(0, 6))
        self.language_var = ctk.StringVar(value="Loading...")
        self.language_menu = ctk.CTkOptionMenu(lang_frame, variable=self.language_var, values=["Loading..."], command=self._on_language_change, dynamic_resizing=False, **menu_kwargs)
        self.language_menu.pack(fill="x")

        # Voice
        voice_frame = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        voice_frame.grid(row=0, column=1, padx=20, pady=15, sticky="ew")
        ctk.CTkLabel(voice_frame, text="🗣 Voice", font=ctk.CTkFont(size=13, weight="bold"), text_color="#D0D0D0").pack(anchor="w", pady=(0, 6))
        self.voice_var = ctk.StringVar(value="Loading...")
        self.voice_menu = ctk.CTkOptionMenu(voice_frame, variable=self.voice_var, values=["Loading..."], dynamic_resizing=False, **menu_kwargs)
        self.voice_menu.pack(fill="x")

        # Format
        fmt_frame = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        fmt_frame.grid(row=0, column=2, padx=20, pady=15, sticky="ew")
        ctk.CTkLabel(fmt_frame, text="💾 Format", font=ctk.CTkFont(size=13, weight="bold"), text_color="#D0D0D0").pack(anchor="w", pady=(0, 6))
        self.format_var = ctk.StringVar(value="mp3")
        self.format_menu = ctk.CTkOptionMenu(fmt_frame, variable=self.format_var, values=["mp3", "wav", "ogg"], dynamic_resizing=False, **menu_kwargs)
        self.format_menu.pack(fill="x")


        # Textbox and Effects Panel
        self.text_frame = ctk.CTkFrame(self.main_frame, fg_color=PANEL_TINT, corner_radius=15, border_width=1, border_color=PANEL_BORDER)
        self.text_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 20))
        self.text_frame.grid_rowconfigure(2, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)

        # Effects toggle
        toolbar_container = ctk.CTkFrame(self.text_frame, fg_color="transparent")
        toolbar_container.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 0))

        self.effects_var = ctk.BooleanVar(value=False)
        self.effects_switch = ctk.CTkSwitch(
            toolbar_container, text="✨ Text Effects", variable=self.effects_var, command=self._on_effects_toggle, 
            font=ctk.CTkFont(weight="bold"), progress_color=ACCENT_COLOR, button_color="#DCE4EE", button_hover_color="#FFFFFF"
        )
        self.effects_switch.pack(side="left")

        self.count_label = ctk.CTkLabel(toolbar_container, text="", font=ctk.CTkFont(size=12), text_color="#8A8A8A")
        self.count_label.pack(side="right")

        # Effects Toolbar (hidden initially)
        self.effects_toolbar = ctk.CTkFrame(self.text_frame, fg_color="transparent")
        
        effect_buttons = [
            ("Pause",       "[pause]",                "Insert a 0.5s pause"),
            ("Long Pause",  "[long pause]",           "Insert a 1.5s pause"),
            ("Whisper",     "[whisper]...[/whisper]",  "Wrap selection in whisper"),
            ("Soft",        "[soft]...[/soft]",        "Wrap selection in soft voice"),
            ("Loud",        "[loud]...[/loud]",        "Wrap selection in loud voice"),
            ("Slow",        "[slow]...[/slow]",        "Wrap selection in slow speech"),
            ("Fast",        "[fast]...[/fast]",        "Wrap selection in fast speech"),
            ("High",        "[high]...[/high]",        "Wrap selection in high pitch"),
            ("Low",         "[low]...[/low]",          "Wrap selection in low pitch"),
        ]

        for label, tag, hint in effect_buttons:
            btn = ctk.CTkButton(
                self.effects_toolbar, text=label, width=0, height=28, corner_radius=8,
                font=ctk.CTkFont(size=11, weight="bold"), fg_color="transparent", hover_color="#1E2030", 
                border_width=1, border_color=PANEL_BORDER, text_color=ACCENT_COLOR,
                command=lambda t=tag, h=hint: self._insert_effect_tag(t, h),
            )
            btn.pack(side="left", padx=3, pady=5)

        # Text input
        self.text_input = ctk.CTkTextbox(
            self.text_frame, font=ctk.CTkFont(size=15, family="Segoe UI"), 
            corner_radius=10, fg_color=INPUT_BG, border_width=1, border_color=PANEL_BORDER,
            text_color="#E0E0E0"
        )
        self.text_input.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 20))
        self.text_input.insert("1.0", "Hello! This is a sample text. Try changing the voice and settings to hear different results.")
        self.text_input.bind("<KeyRelease>", lambda e: self._update_text_counts())
        self._update_text_counts()


        # Bottom Section (Sliders and Waveform)
        self.bottom_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.bottom_frame.grid(row=2, column=0, sticky="ew")
        self.bottom_frame.grid_columnconfigure(1, weight=1)

        # Sliders Panel
        self.sliders_frame = ctk.CTkFrame(self.bottom_frame, fg_color=PANEL_TINT, corner_radius=15, border_width=1, border_color=PANEL_BORDER)
        self.sliders_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        slider_kwargs = {"button_color": ACCENT_COLOR, "button_hover_color": ACCENT_HOVER, "progress_color": ACCENT_COLOR}

        # Rate
        rate_row = ctk.CTkFrame(self.sliders_frame, fg_color="transparent")
        rate_row.pack(fill="x", padx=20, pady=(15, 8))
        ctk.CTkLabel(rate_row, text="⏱ Rate", width=60, anchor="w", font=ctk.CTkFont(size=13, weight="bold"), text_color="#D0D0D0").pack(side="left")
        self.rate_slider = ctk.CTkSlider(rate_row, from_=-50, to=50, number_of_steps=100, command=self._on_rate_change, width=160, **slider_kwargs)
        self.rate_slider.set(0)
        self.rate_slider.pack(side="left", padx=15)
        self.rate_label = ctk.CTkLabel(rate_row, text="+0%", width=40, text_color="#A0A0A0")
        self.rate_label.pack(side="left")

        # Pitch
        pitch_row = ctk.CTkFrame(self.sliders_frame, fg_color="transparent")
        pitch_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(pitch_row, text="🎵 Pitch", width=60, anchor="w", font=ctk.CTkFont(size=13, weight="bold"), text_color="#D0D0D0").pack(side="left")
        self.pitch_slider = ctk.CTkSlider(pitch_row, from_=-50, to=50, number_of_steps=100, command=self._on_pitch_change, width=160, **slider_kwargs)
        self.pitch_slider.set(0)
        self.pitch_slider.pack(side="left", padx=15)
        self.pitch_label = ctk.CTkLabel(pitch_row, text="+0Hz", width=40, text_color="#A0A0A0")
        self.pitch_label.pack(side="left")

        # Volume
        vol_row = ctk.CTkFrame(self.sliders_frame, fg_color="transparent")
        vol_row.pack(fill="x", padx=20, pady=(8, 15))
        ctk.CTkLabel(vol_row, text="🔊 Vol", width=60, anchor="w", font=ctk.CTkFont(size=13, weight="bold"), text_color="#D0D0D0").pack(side="left")
        self.volume_slider = ctk.CTkSlider(vol_row, from_=0, to=100, number_of_steps=100, command=self._on_volume_change, width=160, **slider_kwargs)
        self.volume_slider.set(80)
        self.volume_slider.pack(side="left", padx=15)
        self.volume_label = ctk.CTkLabel(vol_row, text="80%", width=40, text_color="#A0A0A0")
        self.volume_label.pack(side="left")
        pygame.mixer.music.set_volume(0.8)

        # Waveform Panel
        self.waveform_frame = ctk.CTkFrame(self.bottom_frame, fg_color=PANEL_TINT, corner_radius=15, border_width=1, border_color=PANEL_BORDER)
        # Hidden initially - only shows when playing
        
        self.waveform_canvas = tk.Canvas(self.waveform_frame, height=140, bg=BG_COLOR, highlightthickness=0) 
        self.waveform_canvas.pack(fill="both", expand=True, padx=20, pady=20)
        
        # ── Keyboard shortcuts ──────────────────────────────────────────────
        self.bind("<Control-Return>", lambda e: self._on_generate())
        self.bind("<Control-p>", lambda e: self._on_play_pause())
        self.bind("<Control-s>", lambda e: self._on_save())
        self.bind("<Escape>", lambda e: self._on_stop())
        self.bind("<F1>", lambda e: self._show_shortcuts_dialog())

        self._shortcuts_hint = "Shortcuts: Ctrl+Enter=Gen | Ctrl+P=Play | Esc=Stop"

    # ── Voice Loading ────────────────────────────────────────────────────────

    def _load_voices(self):
        """Fetch available voices from edge-tts (runs in background thread)."""
        try:
            loop = asyncio.new_event_loop()
            voices_list = loop.run_until_complete(edge_tts.list_voices())
            loop.close()

            self.voices = sorted(voices_list, key=lambda v: v["ShortName"])

            # Extract unique languages
            lang_set = {}
            for v in self.voices:
                locale = v["Locale"]
                lang = v.get("FriendlyName", locale).split(" ")[0]
                # Build a readable name like "English (US)"
                parts = locale.split("-")
                if len(parts) >= 2:
                    lang_set[locale] = f"{lang} ({locale})"

            # Sort by display name and keep a mapping
            self.lang_display = dict(sorted(lang_set.items(), key=lambda x: x[1]))
            self.languages = list(self.lang_display.keys())

            # Default to en-US if available
            default_locale = "en-US" if "en-US" in self.languages else self.languages[0]

            # Update UI from main thread
            self.after(0, self._populate_language_menu, default_locale)

        except Exception as e:
            self.after(0, self._set_status, f"Error loading voices: {e}")

    def _populate_language_menu(self, default_locale: str):
        display_names = list(self.lang_display.values())
        self.language_menu.configure(values=display_names)

        default_display = self.lang_display[default_locale]
        self.language_var.set(default_display)
        self._on_language_change(default_display)
        self._set_status(self._shortcuts_hint)

    def _on_language_change(self, selected_display: str):
        """Filter voices by selected language."""
        # Find the locale key from display name
        locale = None
        for key, display in self.lang_display.items():
            if display == selected_display:
                locale = key
                break

        if locale is None:
            return

        self.filtered_voices = [v for v in self.voices if v["Locale"] == locale]
        voice_names = [self._voice_display_name(v) for v in self.filtered_voices]

        self.voice_menu.configure(values=voice_names)
        if voice_names:
            self.voice_var.set(voice_names[0])

    def _voice_display_name(self, voice: dict) -> str:
        """Build a display name with gender tag, e.g. 'en-US-GuyNeural [Male]'."""
        name = voice["ShortName"]
        gender = voice.get("Gender", "")
        if gender:
            return f"{name}  [{gender}]"
        return name

    def _selected_voice_short_name(self) -> str:
        """Extract the ShortName from the display string (strip the tag)."""
        display = self.voice_var.get()
        # Remove the trailing '  [Male]' / '  [Female]' etc.
        if "  [" in display:
            return display.split("  [")[0]
        return display

    # ── Text Count ────────────────────────────────────────────────────────────

    def _update_text_counts(self):
        """Update the live character / word count label."""
        text = self.text_input.get("1.0", "end").strip()
        chars = len(text)
        words = len(text.split()) if text else 0
        self.count_label.configure(text=f"{words} words  |  {chars} chars")

    # ── Text Effects Helpers ─────────────────────────────────────────────────

    def _on_effects_toggle(self):
        """Show or hide the Text Effects toolbar."""
        if self.effects_var.get():
            self.effects_toolbar.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 5))
            if not PYDUB_AVAILABLE:
                self._set_status("Warning: ffmpeg not found — effects tags will be stripped. Install ffmpeg for full effects.")
            else:
                self._set_status("Text Effects ON — use toolbar buttons or type tags like [slow]...[/slow]")
        else:
            self.effects_toolbar.grid_remove()
            self._set_status("Text Effects OFF")

    def _insert_effect_tag(self, tag: str, hint: str):
        """Insert an effect tag at the cursor, wrapping any selected text."""
        try:
            sel_start = self.text_input.index("sel.first")
            sel_end = self.text_input.index("sel.last")
            selected = self.text_input.get(sel_start, sel_end)
        except Exception:
            selected = None
            sel_start = None
            sel_end = None

        if selected and "..." in tag:
            wrapped = tag.replace("...", selected)
            self.text_input.delete(sel_start, sel_end)
            self.text_input.insert(sel_start, wrapped)
        elif "..." in tag:
            cursor = self.text_input.index("insert")
            placeholder = "your text here"
            filled = tag.replace("...", placeholder)
            self.text_input.insert(cursor, filled)
            start_idx = self.text_input.search(placeholder, cursor)
            if start_idx:
                end_idx = f"{start_idx}+{len(placeholder)}c"
                self.text_input.tag_add("sel", start_idx, end_idx)
        else:
            self.text_input.insert("insert", tag)

        self._update_text_counts()
        self._set_status(hint)

    @staticmethod
    def _parse_effect_segments(text: str, base_rate: str, base_pitch: str):
        """Parse text with [effect] markers into a list of segments.

        Returns list of tuples:
          ("text",    content_str, {"rate": ..., "pitch": ..., ...})
          ("silence", duration_ms, {})
        """
        segments = []
        last_end = 0

        for match in EFFECTS_PATTERN.finditer(text):
            # Plain text before this marker
            before = text[last_end:match.start()].strip()
            if before:
                segments.append(("text", before, {"rate": base_rate, "pitch": base_pitch}))

            full = match.group(0)
            if full == "[pause]":
                segments.append(("silence", 500, {}))
            elif full == "[long pause]":
                segments.append(("silence", 1500, {}))
            else:
                effect_name = match.group(1)
                inner_text = match.group(2).strip()
                if inner_text:
                    params = {"rate": base_rate, "pitch": base_pitch}
                    params.update(EFFECTS_MAP[effect_name])
                    segments.append(("text", inner_text, params))

            last_end = match.end()

        remaining = text[last_end:].strip()
        if remaining:
            segments.append(("text", remaining, {"rate": base_rate, "pitch": base_pitch}))

        return segments

    # ── Slider Callbacks ─────────────────────────────────────────────────────

    def _on_rate_change(self, value):
        v = int(value)
        sign = "+" if v >= 0 else ""
        self.rate_label.configure(text=f"{sign}{v}%")

    def _on_pitch_change(self, value):
        v = int(value)
        sign = "+" if v >= 0 else ""
        self.pitch_label.configure(text=f"{sign}{v}Hz")

    def _on_volume_change(self, value):
        v = int(value)
        self.volume_label.configure(text=f"{v}%")
        pygame.mixer.music.set_volume(v / 100.0)

    # ── Generation ───────────────────────────────────────────────────────────

    def _on_generate(self):
        text = self.text_input.get("1.0", "end").strip()
        if not text:
            self._set_status("Please enter some text first.")
            return

        voice = self._selected_voice_short_name()
        if voice == "Loading..." or not voice:
            self._set_status("Please wait for voices to load.")
            return

        if self.is_generating:
            return

        self.is_generating = True
        self._stop_playback()
        self.generate_btn.configure(state="disabled", text="⏳ Generating...")
        self._set_status("Generating audio...")

        rate_val = int(self.rate_slider.get())
        pitch_val = int(self.pitch_slider.get())
        rate_str = f"{'+' if rate_val >= 0 else ''}{rate_val}%"
        pitch_str = f"{'+' if pitch_val >= 0 else ''}{pitch_val}Hz"

        use_effects = self.effects_var.get()

        threading.Thread(
            target=self._generate_audio,
            args=(text, voice, rate_str, pitch_str, use_effects),
            daemon=True,
        ).start()

    @staticmethod
    def _strip_effect_markers(text: str) -> str:
        """Remove all effect markers from text, keeping inner content."""
        # Replace [pause] and [long pause] with nothing
        cleaned = re.sub(r'\[pause\]', '', text)
        cleaned = re.sub(r'\[long pause\]', '', cleaned)
        # Replace [effect]content[/effect] with just content
        cleaned = re.sub(rf'\[({_EFFECT_NAMES})\](.*?)\[/\1\]', r'\2', cleaned, flags=re.DOTALL)
        # Clean up extra whitespace
        cleaned = re.sub(r'  +', ' ', cleaned).strip()
        return cleaned

    def _generate_audio(self, text: str, voice: str, rate: str, pitch: str, use_effects: bool = False):
        """Run edge-tts in a background thread. Supports text effects and long text chunking."""
        try:
            has_markers = bool(EFFECTS_PATTERN.search(text))

            if has_markers and use_effects and PYDUB_AVAILABLE:
                # Full effects processing: split into segments and stitch
                tmp_path = self._generate_with_effects(text, voice, rate, pitch)
            else:
                # Simple generation — always strip markers so they aren't read aloud
                clean_text = self._strip_effect_markers(text) if has_markers else text

                # Long text chunking: split if text is very long
                chunks = _chunk_text(clean_text)

                if len(chunks) > 1 and PYDUB_AVAILABLE:
                    # Generate each chunk and stitch together
                    self.after(0, self._set_status, f"Generating audio ({len(chunks)} chunks)...")
                    tmp_path = self._generate_chunked(chunks, voice, rate, pitch)
                else:
                    # Single chunk or no pydub — generate directly
                    if len(chunks) > 1:
                        # No pydub, just use first chunk and warn
                        clean_text = chunks[0]
                        self.after(0, self._set_status, "Text truncated (install ffmpeg for long text support)")

                    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    tmp_path = tmp.name
                    tmp.close()

                    loop = asyncio.new_event_loop()
                    communicate = edge_tts.Communicate(clean_text, voice, rate=rate, pitch=pitch)
                    loop.run_until_complete(communicate.save(tmp_path))
                    loop.close()

            self.current_audio_path = tmp_path
            self._last_gen_meta = {
                "text": text[:80] + ("..." if len(text) > 80 else ""),
                "voice": voice,
                "rate": rate,
                "pitch": pitch,
                "effects": has_markers,
                "path": tmp_path,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            self.after(0, self._on_generate_complete)

        except Exception as e:
            self.after(0, self._on_generate_error, str(e))

    def _generate_with_effects(self, text: str, voice: str, base_rate: str, base_pitch: str) -> str:
        """Parse effect markers, generate each segment, and stitch together with pydub."""
        segments = self._parse_effect_segments(text, base_rate, base_pitch)
        loop = asyncio.new_event_loop()
        combined = AudioSegment.empty()
        temp_files = []

        try:
            for seg_type, content, params in segments:
                if seg_type == "silence":
                    combined += AudioSegment.silent(duration=content)
                elif seg_type == "text" and content:
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    tmp_path = tmp.name
                    tmp.close()
                    temp_files.append(tmp_path)

                    communicate = edge_tts.Communicate(
                        content, voice,
                        rate=params.get("rate", base_rate),
                        pitch=params.get("pitch", base_pitch),
                        volume=params.get("volume", "+0%"),
                    )
                    loop.run_until_complete(communicate.save(tmp_path))
                    combined += AudioSegment.from_mp3(tmp_path)
        finally:
            loop.close()
            # Clean up intermediate temp files
            for f in temp_files:
                try:
                    os.remove(f)
                except OSError:
                    pass

        # Export the stitched result
        out = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        out_path = out.name
        out.close()
        combined.export(out_path, format="mp3")
        return out_path

    def _generate_chunked(self, chunks: list[str], voice: str, rate: str, pitch: str) -> str:
        """Generate audio for each chunk and stitch together using pydub."""
        loop = asyncio.new_event_loop()
        combined = AudioSegment.empty()
        temp_files = []

        try:
            for i, chunk in enumerate(chunks):
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp_path = tmp.name
                tmp.close()
                temp_files.append(tmp_path)

                communicate = edge_tts.Communicate(chunk, voice, rate=rate, pitch=pitch)
                loop.run_until_complete(communicate.save(tmp_path))
                combined += AudioSegment.from_mp3(tmp_path)
                # Brief pause between chunks for natural flow
                combined += AudioSegment.silent(duration=200)
        finally:
            loop.close()
            for f in temp_files:
                try:
                    os.remove(f)
                except OSError:
                    pass

        out = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        out_path = out.name
        out.close()
        combined.export(out_path, format="mp3")
        return out_path

    def _on_generate_complete(self):
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="⚡ Generate")
        self.play_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self.srt_btn.configure(state="normal")
        # Add to history
        if hasattr(self, "_last_gen_meta") and self._last_gen_meta:
            self.history.insert(0, self._last_gen_meta)
            if len(self.history) > 50:  # Cap at 50 entries
                self.history = self.history[:50]
            self._last_gen_meta = None
        # Waveform will be drawn on play
        self._set_status("Audio generated! Click Play to listen or Save As to export.")

    def _on_generate_error(self, error_msg: str):
        self.is_generating = False
        self.generate_btn.configure(state="normal", text="⚡ Generate")
        self._set_status(f"Generation failed: {error_msg}")

    # ── Playback ─────────────────────────────────────────────────────────────

    def _on_play_pause(self):
        if not self.current_audio_path:
            return

        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.play_btn.configure(text="▶")
            self._set_status("Paused")
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.load(self.current_audio_path)
                pygame.mixer.music.play()
            self.is_playing = True
            self.play_btn.configure(text="⏸")
            self._draw_waveform(self.current_audio_path)
            self._set_status("Playing...")
            self._check_playback_end()

    def _on_stop(self):
        self._stop_playback()
        self._set_status("Stopped")

    def _stop_playback(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.play_btn.configure(text="▶")
        self.waveform_frame.grid_forget()

    def _check_playback_end(self):
        """Poll to detect when playback finishes."""
        if self.is_playing and not pygame.mixer.music.get_busy():
            self.is_playing = False
            self.play_btn.configure(text="▶")
            self.waveform_frame.grid_forget()
            self._set_status("Playback finished")
            return
        if self.is_playing:
            self.after(200, self._check_playback_end)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _on_save(self):
        if not self.current_audio_path:
            return

        fmt = self.format_var.get()
        filetypes_map = {
            "mp3": [("MP3 Audio", "*.mp3")],
            "wav": [("WAV Audio", "*.wav")],
            "ogg": [("OGG Audio", "*.ogg")],
        }
        filetypes = filetypes_map.get(fmt, filetypes_map["mp3"]) + [("All Files", "*.*")]

        dest = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=filetypes,
            title="Save Voice Clip",
        )
        if not dest:
            return

        if fmt == "mp3":
            shutil.copy2(self.current_audio_path, dest)
            self._set_status(f"Saved to {dest}")
        elif PYDUB_AVAILABLE:
            try:
                audio = AudioSegment.from_mp3(self.current_audio_path)
                audio.export(dest, format=fmt)
                self._set_status(f"Saved as {fmt.upper()} to {dest}")
            except Exception as e:
                self._set_status(f"Export failed: {e}")
        else:
            self._set_status("Install pydub + ffmpeg for WAV/OGG export")

    # ── Batch Generation ──────────────────────────────────────────────────────

    def _show_batch_dialog(self):
        """Dialog for generating multiple clips — one per line."""
        if self.is_generating:
            self._set_status("Please wait for current generation to finish.")
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Batch Generate")
        dlg.geometry("520x440")
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Batch Generate", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(14, 4))
        ctk.CTkLabel(dlg, text="One line per clip. Each line becomes a separate audio file.", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 8))

        batch_text = ctk.CTkTextbox(dlg, height=200, font=ctk.CTkFont(size=13))
        batch_text.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        # Load from file button
        def load_file():
            path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
            if path:
                with open(path, "r", encoding="utf-8") as f:
                    batch_text.delete("1.0", "end")
                    batch_text.insert("1.0", f.read())

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkButton(btn_row, text="Load .txt File", command=load_file, width=120).pack(side="left")

        # Progress label
        progress_label = ctk.CTkLabel(btn_row, text="", font=ctk.CTkFont(size=12), text_color="gray")
        progress_label.pack(side="left", padx=(12, 0))

        fmt_label = ctk.CTkLabel(btn_row, text=f"Format: {self.format_var.get().upper()}", font=ctk.CTkFont(size=12), text_color="gray")
        fmt_label.pack(side="right")

        # Bottom buttons
        bottom = ctk.CTkFrame(dlg, fg_color="transparent")
        bottom.pack(fill="x", padx=16, pady=(0, 12))

        def start_batch():
            lines = [l.strip() for l in batch_text.get("1.0", "end").strip().splitlines() if l.strip()]
            if not lines:
                progress_label.configure(text="No lines to process.")
                return

            voice = self._selected_voice_short_name()
            if voice == "Loading..." or not voice:
                progress_label.configure(text="Voices not loaded yet.")
                return

            out_dir = filedialog.askdirectory(title="Choose output folder")
            if not out_dir:
                return

            rate_val = int(self.rate_slider.get())
            pitch_val = int(self.pitch_slider.get())
            rate_str = f"{'+' if rate_val >= 0 else ''}{rate_val}%"
            pitch_str = f"{'+' if pitch_val >= 0 else ''}{pitch_val}Hz"
            fmt = self.format_var.get()

            gen_btn.configure(state="disabled")
            cancel_btn.configure(state="normal")
            self.batch_cancel = False

            threading.Thread(
                target=self._run_batch,
                args=(lines, voice, rate_str, pitch_str, fmt, out_dir, progress_label, dlg, gen_btn, cancel_btn),
                daemon=True,
            ).start()

        gen_btn = ctk.CTkButton(bottom, text="Generate All", command=start_batch, width=130, fg_color="#27ae60", hover_color="#2ecc71")
        gen_btn.pack(side="left", padx=(0, 8))

        cancel_btn = ctk.CTkButton(bottom, text="Cancel", command=lambda: setattr(self, 'batch_cancel', True), width=90, state="disabled", fg_color="#c0392b", hover_color="#e74c3c")
        cancel_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(bottom, text="Close", width=90, command=dlg.destroy).pack(side="right")
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _run_batch(self, lines, voice, rate, pitch, fmt, out_dir, progress_label, dlg, gen_btn, cancel_btn):
        """Background batch generation."""
        total = len(lines)
        loop = asyncio.new_event_loop()

        for i, line in enumerate(lines, 1):
            if self.batch_cancel:
                self.after(0, progress_label.configure, {"text": f"Cancelled after {i - 1}/{total}"})
                break

            self.after(0, progress_label.configure, {"text": f"Generating {i}/{total}..."})

            try:
                # Generate to temp MP3 first
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp_path = tmp.name
                tmp.close()

                communicate = edge_tts.Communicate(line, voice, rate=rate, pitch=pitch)
                loop.run_until_complete(communicate.save(tmp_path))

                # Determine output filename
                safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in line[:40]).strip()
                out_path = os.path.join(out_dir, f"{i:03d}_{safe_name}.{fmt}")

                # Convert if needed
                if fmt == "mp3":
                    shutil.move(tmp_path, out_path)
                elif PYDUB_AVAILABLE:
                    audio = AudioSegment.from_mp3(tmp_path)
                    audio.export(out_path, format=fmt)
                    os.remove(tmp_path)
                else:
                    shutil.move(tmp_path, out_path.replace(f".{fmt}", ".mp3"))

            except Exception as e:
                self.after(0, progress_label.configure, {"text": f"Error on line {i}: {e}"})

        loop.close()

        if not self.batch_cancel:
            self.after(0, progress_label.configure, {"text": f"Done! {total} clips saved."})
        self.after(0, gen_btn.configure, {"state": "normal"})
        self.after(0, cancel_btn.configure, {"state": "disabled"})

    # ── History Dialog ────────────────────────────────────────────────────────

    def _show_history_dialog(self):
        """Show recent generated clips with the ability to replay them."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Generation History")
        dlg.geometry("500x400")
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Recent Clips", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(14, 8))

        if not self.history:
            ctk.CTkLabel(dlg, text="No clips generated yet.", font=ctk.CTkFont(size=13), text_color="gray").pack(pady=20)
            ctk.CTkButton(dlg, text="Close", width=100, command=dlg.destroy).pack(pady=(0, 12))
            dlg.bind("<Escape>", lambda e: dlg.destroy())
            return

        scroll = ctk.CTkScrollableFrame(dlg)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        for entry in self.history:
            item = ctk.CTkFrame(scroll)
            item.pack(fill="x", pady=3, padx=2)

            # Info column
            info = ctk.CTkFrame(item, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

            text_preview = entry.get("text", "")
            fx_tag = " [FX]" if entry.get("effects") else ""
            ctk.CTkLabel(info, text=f'"{text_preview}"{fx_tag}', anchor="w", font=ctk.CTkFont(size=12)).pack(fill="x")
            meta = f"{entry.get('voice', '?')}  |  {entry.get('rate', '')}  |  {entry.get('pitch', '')}  |  {entry.get('timestamp', '')}"
            ctk.CTkLabel(info, text=meta, anchor="w", font=ctk.CTkFont(size=11), text_color="gray").pack(fill="x")

            # Play button
            audio_path = entry.get("path", "")
            if audio_path and os.path.exists(audio_path):
                def make_play(p=audio_path):
                    def play_clip():
                        self._stop_playback()
                        self.current_audio_path = p
                        self.play_btn.configure(state="normal")
                        self.stop_btn.configure(state="normal")
                        self.save_btn.configure(state="normal")
                        pygame.mixer.music.load(p)
                        pygame.mixer.music.play()
                        self.is_playing = True
                        self.play_btn.configure(text="⏸")
                        self._set_status("Playing from history...")
                        self._check_playback_end()
                    return play_clip

                ctk.CTkButton(item, text="Play", width=60, height=30, command=make_play()).pack(side="right", padx=(4, 8), pady=6)

        bottom = ctk.CTkFrame(dlg, fg_color="transparent")
        bottom.pack(fill="x", padx=12, pady=(0, 12))

        def clear_history():
            self.history.clear()
            dlg.destroy()
            self._set_status("History cleared.")

        ctk.CTkButton(bottom, text="Clear History", width=110, fg_color="#c0392b", hover_color="#e74c3c", command=clear_history).pack(side="left")
        ctk.CTkButton(bottom, text="Close", width=100, command=dlg.destroy).pack(side="right")
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    # ── Shortcuts Dialog ─────────────────────────────────────────────────────

    def _show_shortcuts_dialog(self):
        """Open a top-level window listing all keyboard shortcuts."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Keyboard Shortcuts")
        dlg.geometry("340x280")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Keyboard Shortcuts", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(18, 14))

        shortcuts = [
            ("Ctrl + Enter", "Generate audio"),
            ("Ctrl + P", "Play / Pause"),
            ("Escape", "Stop playback"),
            ("Ctrl + S", "Save As..."),
            ("F1", "Show this help"),
        ]

        for key, action in shortcuts:
            row = ctk.CTkFrame(dlg, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(row, text=key, width=120, anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left")
            ctk.CTkLabel(row, text=action, anchor="w", font=ctk.CTkFont(size=13), text_color="gray").pack(side="left")

        ctk.CTkButton(dlg, text="Close", width=100, command=dlg.destroy).pack(pady=(16, 12))

        # Allow Escape to close the dialog too
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.bind("<F1>", lambda e: dlg.destroy())

    # ── Waveform Visualizer ──────────────────────────────────────────────────

    def _draw_waveform_placeholder(self):
        """Draw a flat-line placeholder when no audio is loaded."""
        self.waveform_canvas.delete("all")
        w = self.waveform_canvas.winfo_width() or 900
        h = 80
        mid = h // 2
        self.waveform_canvas.create_line(0, mid, w, mid, fill="#1E2030", width=2)
        self.waveform_canvas.create_text(w // 2, mid, text="No waveform — generate audio first", fill="#7f8c8d", font=("Segoe UI", 12))

    def _draw_waveform(self, audio_path: str):
        """Draw a waveform from an audio file on the canvas."""
        self.waveform_frame.grid(row=0, column=1, sticky="nsew")
        try:
            # Convert mp3 to wav samples using pydub if available, else use basic display
            samples = self._extract_samples(audio_path)
            if not samples:
                self._draw_waveform_placeholder()
                return

            self.waveform_canvas.delete("all")
            self.waveform_canvas.update_idletasks()
            w = self.waveform_canvas.winfo_width() or 900
            h = 80
            mid = h // 2

            # Downsample to fit canvas width
            num_bars = min(w, len(samples))
            step = max(1, len(samples) // num_bars)

            # Aggregate by chunks
            bars = []
            for i in range(0, len(samples), step):
                chunk = samples[i:i + step]
                if chunk:
                    bars.append(max(abs(s) for s in chunk))
                if len(bars) >= num_bars:
                    break

            if not bars:
                self._draw_waveform_placeholder()
                return

            max_val = max(bars) or 1
            bar_width = max(1, w / len(bars))

            for i, amplitude in enumerate(bars):
                norm = amplitude / max_val
                bar_h = max(1, int(norm * (mid - 2)))
                x = i * bar_width
                # Draw symmetric bar
                color = self._waveform_color(norm)
                self.waveform_canvas.create_line(x, mid - bar_h, x, mid + bar_h, fill=color, width=max(2.0, bar_width * 0.8), capstyle="round")

        except Exception:
            self._draw_waveform_placeholder()

    @staticmethod
    def _waveform_color(normalized: float) -> str:
        """Return a vibrant gradient color from purple to bright cyan (loud)."""
        r = int(123 + normalized * (59 - 123))
        g = int(97 + normalized * (130 - 97))
        b = int(255 + normalized * (246 - 255))
        return f"#{min(max(r, 0), 255):02x}{min(max(g, 0), 255):02x}{min(max(b, 0), 255):02x}"

    @staticmethod
    def _extract_samples(audio_path: str) -> list[int]:
        """Extract raw PCM samples from an audio file."""
        # Try pydub first (needs ffmpeg)
        if PYDUB_AVAILABLE:
            try:
                audio = AudioSegment.from_file(audio_path)
                audio = audio.set_channels(1).set_sample_width(2)
                raw = audio.raw_data
                return list(struct.unpack(f"<{len(raw) // 2}h", raw))
            except Exception:
                pass

        # Fallback: use pygame.mixer.Sound to decode the MP3 into raw PCM
        try:
            snd = pygame.mixer.Sound(file=audio_path)
            raw = snd.get_raw()
            if not raw:
                return []
            # pygame mixer defaults: 16-bit signed, usually stereo (2 channels)
            freq, bits, channels = pygame.mixer.get_init()
            sample_width = abs(bits) // 8  # bits can be negative (signed)
            if sample_width == 2:
                all_samples = list(struct.unpack(f"<{len(raw) // 2}h", raw))
            elif sample_width == 1:
                all_samples = list(struct.unpack(f"{len(raw)}b", raw))
            else:
                return []
            # If stereo, take every Nth sample for mono
            if channels >= 2:
                all_samples = all_samples[::channels]
            return all_samples
        except Exception:
            pass

        return []

    # ── Presets / Bookmarks ──────────────────────────────────────────────────

    def _load_presets(self) -> list[dict]:
        """Load presets from JSON file."""
        if os.path.exists(_PRESETS_FILE):
            try:
                with open(_PRESETS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _save_presets(self, presets: list[dict]):
        """Persist presets to JSON file."""
        try:
            with open(_PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(presets, f, indent=2)
        except Exception as e:
            self._set_status(f"Error saving presets: {e}")

    def _show_presets_dialog(self):
        """Show preset management dialog."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Voice Presets")
        dlg.geometry("460x420")
        dlg.resizable(True, True)
        dlg.transient(self)
        dlg.grab_set()

        ctk.CTkLabel(dlg, text="Voice Presets", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(14, 4))
        ctk.CTkLabel(dlg, text="Save and recall your favorite voice configurations.", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 8))

        # Save current as preset
        save_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        save_frame.pack(fill="x", padx=16, pady=(0, 8))

        self._preset_name_entry = ctk.CTkEntry(save_frame, placeholder_text="Preset name...", width=260)
        self._preset_name_entry.pack(side="left", padx=(0, 8))

        def save_current():
            name = self._preset_name_entry.get().strip()
            if not name:
                return
            preset = {
                "name": name,
                "voice": self._selected_voice_short_name(),
                "language": self.language_var.get(),
                "rate": int(self.rate_slider.get()),
                "pitch": int(self.pitch_slider.get()),
                "volume": int(self.volume_slider.get()),
                "effects": self.effects_var.get(),
                "format": self.format_var.get(),
            }
            presets = self._load_presets()
            presets.append(preset)
            self._save_presets(presets)
            self._preset_name_entry.delete(0, "end")
            refresh_list()
            self._set_status(f"Preset '{name}' saved!")

        ctk.CTkButton(save_frame, text="Save Current", command=save_current, width=130, fg_color="#27ae60", hover_color="#2ecc71").pack(side="left")

        # Preset list
        scroll = ctk.CTkScrollableFrame(dlg)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        def refresh_list():
            for child in scroll.winfo_children():
                child.destroy()

            presets = self._load_presets()
            if not presets:
                ctk.CTkLabel(scroll, text="No presets saved yet.", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=12)
                return

            for idx, p in enumerate(presets):
                item = ctk.CTkFrame(scroll)
                item.pack(fill="x", pady=3, padx=2)

                info = ctk.CTkFrame(item, fg_color="transparent")
                info.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=6)

                ctk.CTkLabel(info, text=p.get("name", "Unnamed"), anchor="w", font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x")
                details = f"{p.get('voice', '?')}  |  Rate: {p.get('rate', 0):+d}%  |  Pitch: {p.get('pitch', 0):+d}Hz"
                ctk.CTkLabel(info, text=details, anchor="w", font=ctk.CTkFont(size=11), text_color="gray").pack(fill="x")

                btn_frame = ctk.CTkFrame(item, fg_color="transparent")
                btn_frame.pack(side="right", padx=(4, 8), pady=6)

                def make_load(preset=p):
                    def load():
                        self._apply_preset(preset)
                        dlg.destroy()
                    return load

                def make_delete(i=idx):
                    def delete():
                        presets = self._load_presets()
                        if 0 <= i < len(presets):
                            presets.pop(i)
                            self._save_presets(presets)
                        refresh_list()
                    return delete

                ctk.CTkButton(btn_frame, text="Load", width=55, height=28, command=make_load()).pack(side="left", padx=2)
                ctk.CTkButton(btn_frame, text="X", width=30, height=28, fg_color="#c0392b", hover_color="#e74c3c", command=make_delete()).pack(side="left", padx=2)

        refresh_list()

        ctk.CTkButton(dlg, text="Close", width=100, command=dlg.destroy).pack(pady=(0, 12))
        dlg.bind("<Escape>", lambda e: dlg.destroy())

    def _apply_preset(self, preset: dict):
        """Apply a saved preset to the current settings."""
        # Set language first (this triggers voice list update)
        lang_display = preset.get("language", "")
        if lang_display and lang_display in [self.lang_display.get(k, "") for k in self.languages]:
            self.language_var.set(lang_display)
            self._on_language_change(lang_display)

        # Set voice
        voice_name = preset.get("voice", "")
        for v in self.filtered_voices:
            display = self._voice_display_name(v)
            if v["ShortName"] == voice_name:
                self.voice_var.set(display)
                break

        # Set sliders
        self.rate_slider.set(preset.get("rate", 0))
        self._on_rate_change(preset.get("rate", 0))
        self.pitch_slider.set(preset.get("pitch", 0))
        self._on_pitch_change(preset.get("pitch", 0))
        self.volume_slider.set(preset.get("volume", 80))
        self._on_volume_change(preset.get("volume", 80))

        # Set effects and format
        self.effects_var.set(preset.get("effects", False))
        self._on_effects_toggle()
        self.format_var.set(preset.get("format", "mp3"))

        self._set_status(f"Loaded preset: {preset.get('name', 'Unnamed')}")

    # ── Subtitle / SRT Export ────────────────────────────────────────────────

    def _on_export_srt(self):
        """Export an SRT subtitle file using edge-tts word boundary events."""
        if not self.current_audio_path:
            return

        text = self.text_input.get("1.0", "end").strip()
        if not text:
            self._set_status("No text to generate subtitles for.")
            return

        voice = self._selected_voice_short_name()
        rate_val = int(self.rate_slider.get())
        pitch_val = int(self.pitch_slider.get())
        rate_str = f"{'+' if rate_val >= 0 else ''}{rate_val}%"
        pitch_str = f"{'+' if pitch_val >= 0 else ''}{pitch_val}Hz"

        # Strip effect markers for SRT
        clean_text = self._strip_effect_markers(text)

        dest = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT Subtitle", "*.srt"), ("All Files", "*.*")],
            title="Export SRT Subtitles",
        )
        if not dest:
            return

        self._set_status("Generating subtitles...")
        threading.Thread(
            target=self._generate_srt,
            args=(clean_text, voice, rate_str, pitch_str, dest),
            daemon=True,
        ).start()

    def _generate_srt(self, text: str, voice: str, rate: str, pitch: str, dest: str):
        """Generate an SRT file by collecting word boundaries from edge-tts."""
        try:
            loop = asyncio.new_event_loop()
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)

            # Collect word boundaries
            boundaries: list[dict] = []

            async def collect_events():
                async for event in communicate.stream():
                    if event["type"] == "WordBoundary":
                        boundaries.append({
                            "offset": event["offset"],  # microseconds from start
                            "duration": event["duration"],  # microseconds
                            "text": event["text"],
                        })

            loop.run_until_complete(collect_events())
            loop.close()

            # Group words into subtitle lines (~8-12 words each)
            srt_entries = []
            group: list[dict] = []
            words_per_line = 10

            for b in boundaries:
                group.append(b)
                if len(group) >= words_per_line:
                    srt_entries.append(self._make_srt_entry(len(srt_entries) + 1, group))
                    group = []

            if group:
                srt_entries.append(self._make_srt_entry(len(srt_entries) + 1, group))

            # Write SRT file
            with open(dest, "w", encoding="utf-8") as f:
                f.write("\n".join(srt_entries))

            self.after(0, self._set_status, f"SRT saved to {dest}")

        except Exception as e:
            self.after(0, self._set_status, f"SRT export failed: {e}")

    @staticmethod
    def _make_srt_entry(index: int, group: list[dict]) -> str:
        """Create a single SRT entry from a group of word boundary events."""
        start_us = group[0]["offset"]
        end_us = group[-1]["offset"] + group[-1]["duration"]
        text = " ".join(g["text"] for g in group)

        def fmt_time(us: int) -> str:
            total_ms = us // 10000  # Convert 100ns ticks to ms
            hrs = total_ms // 3600000
            mins = (total_ms % 3600000) // 60000
            secs = (total_ms % 60000) // 1000
            ms = total_ms % 1000
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

        return f"{index}\n{fmt_time(start_us)} --> {fmt_time(end_us)}\n{text}\n"

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    def on_closing(self):
        """Clean up on exit."""
        self._stop_playback()
        pygame.mixer.quit()
        # Clean up all temp files (current + history)
        paths_to_clean = set()
        if self.current_audio_path:
            paths_to_clean.add(self.current_audio_path)
        for entry in self.history:
            p = entry.get("path", "")
            if p:
                paths_to_clean.add(p)
        for p in paths_to_clean:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        self.destroy()


# ── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = VoiceGeneratorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
