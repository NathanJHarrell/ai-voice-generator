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

## Setup

### 1. Install Python

You need Python 3.10 or newer. If you don't have it yet, follow the instructions for your platform below.

#### Windows

Download the installer from [python.org/downloads](https://www.python.org/downloads/). During installation, **check the box that says "Add Python to PATH"** — this is important. Once installed, open PowerShell and verify:

```powershell
python --version
```

> **Note:** On Windows, use `python` (not `python3`).

#### macOS

Python 3 can be installed with Homebrew:

```bash
brew install python
```

Or download the installer from [python.org/downloads](https://www.python.org/downloads/). Verify:

```bash
python3 --version
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3 python3-pip python3-tk
```

Verify:

```bash
python3 --version
```

> **Note:** On Linux, you also need `python3-tk` for the GUI. On Fedora/RHEL, use `sudo dnf install python3-tkinter` instead.

### 2. Install Dependencies

#### Windows

```powershell
pip install edge-tts customtkinter pygame pydub
```

#### macOS / Linux

```bash
pip3 install edge-tts customtkinter pygame pydub
```

### 3. Install ffmpeg (Optional but Recommended)

ffmpeg enables text effects, WAV/OGG export, long text stitching, and enhanced waveform display. The app works without it, but these features will be limited.

#### Windows

```powershell
winget install Gyan.FFmpeg
```

After installing, **close and reopen PowerShell** for the PATH to update. Alternatively, the app will attempt to auto-detect ffmpeg on your system or download a portable copy on first run.

#### macOS

```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian)

```bash
sudo apt install ffmpeg
```

## Usage

#### Windows

```powershell
python voice_generator.py
```

#### macOS / Linux

```bash
python3 voice_generator.py
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
- Internet connection (edge-tts uses Microsoft's online TTS service)
- ffmpeg (optional, for advanced features)
- Windows, macOS, or Linux

## License

MIT — see [LICENSE](LICENSE) for details.
