# Release 1.1 — GUI Improvements
- Modernized UI layout with a sidebar structure
- New dark glassy CustomTkinter theme
- Added vibrant accent colors and media control buttons
- Optimized window size and responsive design

# Release 1.0 — Base Application

The first release of AI Voice Generator, a free and open-source desktop app for generating natural-sounding voice clips using Microsoft Edge's text-to-speech engine.

## Core Features

**Voice Generation** — Access 100+ voices across 40+ languages powered by edge-tts. Adjust speech rate, pitch, and playback volume with real-time sliders.

**Text Effects** — Apply dynamic effects to your text using simple tags: `[pause]`, `[whisper]...[/whisper]`, `[slow]...[/slow]`, `[fast]...[/fast]`, `[loud]...[/loud]`, `[high]...[/high]`, `[low]...[/low]`, and more. A built-in toolbar makes inserting tags easy — just click a button or highlight text and wrap it.

**Waveform Visualizer** — See a color-graded waveform of your generated audio directly in the app. Works with or without ffmpeg installed.

**Batch Generation** — Generate multiple voice clips at once. Enter one line per clip, or load from a `.txt` file. All clips are saved to a folder of your choice with progress tracking and cancel support.

**Voice Presets** — Save your favorite voice + settings combinations and recall them instantly. Presets store voice, language, rate, pitch, volume, effects toggle, and output format.

**Long Text Chunking** — Automatically splits text longer than 2,000 characters at sentence boundaries, generates each chunk separately, and stitches them together seamlessly. No more failed generations on long passages.

**Subtitle/SRT Export** — Generate properly-timed `.srt` subtitle files alongside your audio using edge-tts word boundary events. Perfect for video captioning.

**Multiple Output Formats** — Save as MP3 (default), WAV, or OGG.

**Generation History** — Browse and replay your recent clips (up to 50) without regenerating. Includes voice, rate, pitch, and timestamp metadata.

**Keyboard Shortcuts** — Ctrl+Enter to generate, Ctrl+P to play/pause, Escape to stop, Ctrl+S to save, F1 for help. A visual shortcuts dialog is accessible via the "?" button.

## Requirements

- Python 3.10+ ([download here](https://www.python.org/downloads/))
- Internet connection (edge-tts uses Microsoft's online TTS service)
- ffmpeg (optional, enables text effects, WAV/OGG export, long text stitching, and pydub-based waveform)

## Quick Start

### Windows

```powershell
pip install edge-tts customtkinter pygame pydub
python voice_generator.py
```

> **Note:** Use `python`, not `python3`, on Windows. When installing Python, make sure to check **"Add Python to PATH"**.

### macOS

```bash
brew install python ffmpeg
pip3 install edge-tts customtkinter pygame pydub
python3 voice_generator.py
```

### Linux (Ubuntu/Debian)

```bash
sudo apt install python3 python3-pip python3-tk ffmpeg
pip3 install edge-tts customtkinter pygame pydub
python3 voice_generator.py
```

For detailed setup instructions, see the [README](https://github.com/natethemighty1/ai-voice-generator#setup).

## What's Next

This is the foundation. Future releases may include additional voices, theme customization, audio post-processing, and more. Contributions and feedback are welcome!
