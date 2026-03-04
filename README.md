# AI Voice Generator

A desktop application for generating natural-sounding voice clips using Microsoft Edge's text-to-speech engine.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **100+ voices** across 40+ languages via edge-tts
- **Text Effects** — apply whisper, slow, fast, high/low pitch, and pauses using simple tags
- **Waveform visualizer** — see your audio waveform after generation
- **Batch generation** — generate multiple clips at once (one per line)
- **Voice presets** — save and recall your favorite voice configurations
- **Long text chunking** — automatically splits long text into chunks for reliable generation
- **Subtitle/SRT export** — generate timestamped subtitle files
- **Multiple output formats** — MP3, WAV, and OGG
- **Generation history** — replay and manage recent clips
- **Keyboard shortcuts** — Ctrl+Enter to generate, Ctrl+P to play, and more

## Installation

```bash
pip install edge-tts customtkinter pygame pydub
```

For full feature support (text effects, WAV/OGG export, waveform with pydub), install ffmpeg:

```bash
winget install Gyan.FFmpeg
```

> The app will auto-detect ffmpeg on your system or attempt to download a portable copy on first run.

## Usage

```bash
python voice_generator.py
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl + Enter | Generate audio |
| Ctrl + P | Play / Pause |
| Escape | Stop playback |
| Ctrl + S | Save As |
| F1 | Show shortcuts |

## Text Effects

Enable "Text Effects" and use tags in your text:

- `[pause]` — 0.5s silence
- `[long pause]` — 1.5s silence
- `[slow]...[/slow]` — slower speech
- `[fast]...[/fast]` — faster speech
- `[whisper]...[/whisper]` — very quiet
- `[loud]...[/loud]` — louder voice
- `[high]...[/high]` — higher pitch
- `[low]...[/low]` — lower pitch

## Requirements

- Python 3.10+
- Windows/macOS/Linux (edge-tts requires internet connection)
- ffmpeg (optional, for advanced features)
