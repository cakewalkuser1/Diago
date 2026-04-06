# Diago — Automotive AI Diagnostics + Service Marketplace

Diago is a **web-first, mobile-ready** platform for automotive diagnostics that combines:

- **AI-assisted vehicle issue detection** (audio + OBD context)
- **Service fulfillment workflows** (mobile mechanics today, extensible to towing/locksmith)
- **Future enterprise/fleet analytics tiers**

The product direction is to support:

1. **Consumers** (diagnose and get help quickly)
2. **Service providers** (mobile mechanics and partner providers)
3. **Enterprise accounts** (shops/fleets with reporting and operational tooling)

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Requirements](#requirements)
- [Quick Start (Web UI)](#quick-start-web-ui)
- [Other Ways to Run](#other-ways-to-run)
- [Workflow](#workflow)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## Features

- **Audio Recording & Import**: Record from microphone or import WAV/MP3/FLAC files
- **Spectrogram Visualization**: Real-time STFT and Mel spectrogram display
- **Digital Fingerprinting**: Constellation-map based audio fingerprinting tuned for automotive sounds
- **Fault Matching**: Compare audio against a database of known fault signatures
- **Trouble Code Integration**: Enter OBD-II codes (P/B/C/U) with lookup and NHTSA/Car API fallback
- **Vehicle Context**: VIN decode, recalls, and TSB search (NHTSA + local TSBs)
- **Session Management**: Save and review past analysis sessions
- **Report Export**: Export diagnostic reports as text files

## Architecture Overview

Diago is currently delivered as a modular monorepo.

```text
Frontend (React + Vite)
  -> calls FastAPI endpoints
API (FastAPI service in api/)
  -> orchestrates use-cases and auth/rate limiting
Core (domain logic in core/)
  -> performs diagnostics/fingerprinting/reasoning
Database (database/)
  -> persistence for signatures, sessions, and reference data
```

### Mobile-friendly direction

The current implementation prioritizes web delivery while preserving a backend/API split that supports:

- Android and iOS clients (future)
- Potential service-provider apps
- Future enterprise dashboards

For deeper details, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

- Python 3.10+
- Node.js 18+ (for the web frontend)
- FFmpeg (optional, for MP3 support via pydub)

## Quick Start (Web UI)

1. **Backend** — From the project root:
   ```bash
   pip install -r requirements.txt
   uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. **Frontend** — In another terminal:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Open **http://localhost:5173** in your browser.

The app talks to the API at `http://127.0.0.1:8000` (Vite proxies in dev).

See [frontend/README.md](frontend/README.md) for frontend-specific options.

Copy `.env.example` to `.env` and set optional keys (e.g. `CAR_API_KEY`) for external integrations.

## Other Ways to Run

- **Legacy desktop (PyQt6):** `python main.py` — classic local UI, no API.
- **Tauri desktop / mobile:** The React app can be packaged with Tauri or Capacitor when ready to target desktop/mobile.

## Workflow

1. **Record or import** audio from the vehicle
2. **Enter trouble codes** from an OBD-II scanner
3. Optionally **decode VIN** and review recalls/TSBs
4. Click **Analyze & Match** to compare against known signatures
5. Review **ranked results** and confidence
6. **Save session** or **export report**

## Project Structure

```text
api/                    FastAPI service (primary backend for web)
  main.py               App entry, CORS, routers
  routes/               vehicle, codes, tsb, diagnosis, sessions, etc.
  services/             external integrations
core/                   Shared diagnostic engine (no GUI)
  config.py             Settings (env, paths, API keys)
  audio_io.py, spectrogram.py, fingerprint.py, matcher.py
database/               SQLite data, schema, seed scripts, reference datasets
frontend/               React + TypeScript + Vite (web UI)
main.py                 Legacy PyQt6 desktop entry
gui/                    Legacy PyQt6 UI components
scripts/                Setup and utility scripts
tests/                  Automated tests
```

## Testing

Run tests from the project root:

```bash
pytest -q
```

> If tests fail due to missing local dependencies, install from `requirements.txt` first.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening issues or pull requests.

By participating, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## Security

For vulnerability reporting and security posture notes, see [SECURITY.md](SECURITY.md).

## License

MIT License
