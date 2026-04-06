# Diago Architecture Overview

This document explains the current system architecture and near-term direction.

## Current Architecture

```text
[React + Vite Frontend]
        |
        v
[FastAPI API Layer]
        |
        v
[Core Diagnostic Modules]
        |
        v
[Database + Reference Data]
```

### 1) Frontend (`frontend/`)

- Built with React + TypeScript + Vite
- Handles user interaction for audio upload/recording, diagnostics display, and session workflows
- Communicates with backend over HTTP APIs

### 2) API Layer (`api/`)

- Built with FastAPI
- Provides endpoint routing, request validation, auth middleware, and rate limiting
- Orchestrates calls into core diagnostic services and data access

### 3) Core Domain (`core/`)

- Contains vehicle diagnostics logic (audio preprocessing, spectrogram/fingerprinting, matching, reasoning)
- Keeps business logic separate from transport/UI concerns

### 4) Persistence (`database/`)

- Stores signatures, sessions, and reference datasets (e.g., OBD code mappings)
- Seeds and migration scripts support deterministic startup initialization

## Why this split matters

- Enables independent iteration of UI, API, and diagnostic engine
- Supports future client apps (Android/iOS/provider dashboards) without rewriting core logic
- Improves long-term maintainability and testing strategy

## Planned Evolution (Product direction)

Diago is intended to evolve toward a multi-surface platform:

- **Consumer app**: Web-first now, mobile clients next
- **Provider workflows**: Mobile mechanic operations and dispatch lifecycle
- **Enterprise tier**: Reporting and insights for shops/fleets

The current modular boundaries are intended to support this evolution incrementally.
