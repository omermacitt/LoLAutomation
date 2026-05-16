# RunePilot — Developer Guide

## Project Overview

RunePilot is a Windows desktop automation tool for League of Legends. It auto-picks champions, applies rune pages, sets summoner spells, selects skins, and manages auto-queue. It also automates Riot Client login for multiple saved accounts.

The application runs a FastAPI HTTP server in a background thread and a PyQt6 desktop GUI in the main thread. The GUI communicates with the server via HTTP, keeping UI and automation logic fully decoupled.

---

## How to Run

```bash
# Full app (GUI + API backend)
python run_app.py

# API only (no GUI — development / testing)
python main.py

# Build Windows EXE
python -m PyInstaller --clean -y run_app.spec
```

The FastAPI server listens on `http://127.0.0.1:8000`.

---

## Architecture

Six-layer Clean Architecture under `src/rune_pilot/`:

```
presentation/ (PyQt6)
      |
      | HTTP (requests)
      v
composition/ (FastAPI routing)
      |
      v
application/ (use cases, orchestration)
      |            |
      v            v
infrastructure/  domain/
(LCU, Riot,     (pure models,
 crypto, scraper) constants, helpers)
      |
      | (all layers may use)
      v
    shared/
```

**Layer rule**: Each layer may only import from layers below it. `presentation/` never imports from `infrastructure/` or `domain/` directly — it goes through `application/`. `domain/` is pure Python with no I/O.

---

## Layer Descriptions

| Layer | Path | Responsibility |
|-------|------|----------------|
| `shared/` | `src/rune_pilot/shared/` | App-wide constants, config paths, logging helpers, resource paths, updater. No business logic. No external I/O except log file writes. |
| `domain/` | `src/rune_pilot/domain/` | Pure business logic. Pydantic models, game constants (rune style IDs, spell IDs, roles), ID normalization. Zero LCU or file I/O. |
| `infrastructure/` | `src/rune_pilot/infrastructure/` | All external I/O: LCU HTTP client (lockfile auth), Riot Client UI automation (pyautogui/clipboard), Selenium scraper, password crypto, rune data file loader. |
| `application/` | `src/rune_pilot/application/` | Orchestration and use cases. Automation loop, account management, champion/skin/perk LCU queries. Imports from both `domain/` and `infrastructure/`. |
| `presentation/` | `src/rune_pilot/presentation/` | PyQt6 UI only. Talks to the FastAPI backend over HTTP. Uses `application/` query helpers for champion/skin/perk data that must be loaded synchronously. |
| `composition/` | `src/rune_pilot/composition/` | FastAPI app wiring. `create_app()` builds the app; `register_routes()` adds endpoints. |

---

## Key Files

| File | Purpose |
|------|---------|
| `run_app.py` | Main entry point — starts FastAPI thread + PyQt6 GUI |
| `src/rune_pilot/composition/api_app.py` | `create_app()` — builds the FastAPI instance |
| `src/rune_pilot/composition/endpoints.py` | FastAPI routes: `/health`, `/champions`, `/start_automation`, `/stop_automation` |
| `src/rune_pilot/application/automation.py` | Core automation loop (champion select, runes, spells, skins) |
| `src/rune_pilot/presentation/main_window.py` | Main PyQt6 window (~82 KB) |
| `src/rune_pilot/domain/models.py` | `AutomationConfig` — the Pydantic model passed from GUI to API |

---

## Configuration & Data

| Item | Location |
|------|----------|
| User config | `%APPDATA%\RunePilot\user_config.json` |
| App log | `%APPDATA%\RunePilot\run_app.log` |
| Rune data | `runes.json` in project root (bundled via PyInstaller spec) |
| LCU lockfile | Auto-detected; override with `LOL_LOCKFILE` env var |

---

## Dev Workflow

**Adding a new automation feature:**
1. Add logic in `src/rune_pilot/application/automation.py`
2. If it needs GUI control, add a FastAPI endpoint in `src/rune_pilot/composition/endpoints.py`
3. Add the UI control in `src/rune_pilot/presentation/main_window.py`
4. The GUI calls the endpoint via `requests` (not by importing application code directly)

**Adding a new LCU query used by the UI:**
1. Add the function to the appropriate `application/` query module (`champion_query.py`, `skin_query.py`, `perk_query.py`, or `lobby_service.py`)
2. Import and call it from `presentation/` — never import `lcu_request` directly in presentation

**Adding a new account feature:**
- Logic goes in `src/rune_pilot/application/account_service.py`
- UI goes in `src/rune_pilot/presentation/login_window.py`

---

## Known Architectural Debt

- **Module-level globals** in `application/automation.py` (`RUNNING`, `CURRENT_CONFIG`, `AUTOMATION_THREAD`, `AUTOMATION_LOCK`). Candidate for refactor to an `AutomationService` class injected at startup via `composition/`.
- **Selenium scraper** (`infrastructure/scraper.py`) hardcodes OP.GG XPaths. These break when OP.GG updates their layout. The scraper is a dev-time tool only (not bundled in the EXE).
- **Legacy root files** (`api.py`, `desktop_app.py`, `lcu.py`, `runes_dialog.py`, `rune_presets_dialog.py`, `skins_dialog.py`, `webscrapping.py`) are the original monolithic implementation. They are not imported by anything and can be deleted when no longer needed for reference.
