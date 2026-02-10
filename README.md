# Automotive Audio Spectrogram Analyzer

A desktop application for automotive diagnostics that uses audio spectrogram analysis and digital fingerprinting to identify engine and vehicle faults, paired with OBD-II trouble codes.

## Features

- **Audio Recording & Import**: Record from microphone or import WAV/MP3/FLAC files
- **Spectrogram Visualization**: Real-time STFT and Mel spectrogram display
- **Digital Fingerprinting**: Constellation-map based audio fingerprinting tuned for automotive sounds
- **Fault Matching**: Compare audio against a database of known fault signatures
- **Trouble Code Integration**: Enter OBD-II codes (P/B/C/U) and associate with audio analysis
- **Session Management**: Save and review past analysis sessions
- **Report Export**: Export diagnostic reports as text files

## Requirements

- Python 3.10+
- FFmpeg (required for MP3 support via pydub)

## Installation

1. Clone or download this project.

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Install FFmpeg for MP3 support:
   - **Windows**: Download from https://ffmpeg.org/download.html and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg`

## Usage

Run the application:

```bash
python main.py
```

### Workflow

1. **Record or Import** audio from the vehicle (engine running, driving, etc.)
2. **Enter Trouble Codes** from your OBD-II scanner (e.g., P0301, P0420)
3. Click **Analyze & Match** to fingerprint the audio and compare against known fault signatures
4. Review **Match Results** ranked by confidence percentage
5. **Save Session** or **Export Report** for your records

## Project Structure

```
main.py                  - Application entry point
core/
  audio_io.py            - Microphone recording and file loading
  spectrogram.py         - STFT/Mel spectrogram computation
  fingerprint.py         - Audio fingerprint generation
  matcher.py             - Fingerprint matching engine
database/
  db_manager.py          - SQLite database operations
  seed_data.py           - Known fault signature seed data
gui/
  main_window.py         - Main application window
  record_panel.py        - Recording and import controls
  spectrogram_widget.py  - Spectrogram visualization
  trouble_code_panel.py  - OBD-II code entry
  results_panel.py       - Match results display
```

## Seed Fault Signatures

The application comes pre-loaded with signatures for common automotive faults:

| Code Range   | Fault Type                        |
|-------------|-----------------------------------|
| P0300-P0312 | Engine misfire patterns           |
| P0171/P0174 | Vacuum/intake leak hiss           |
| P0420       | Catalytic converter / exhaust     |
| P0500-series| Wheel bearing hum                 |
| --          | Belt squeal / alternator whine    |

## License

MIT License
