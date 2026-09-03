# RunePilot

**RunePilot** is a Windows desktop automation tool for League of Legends. It communicates with the League Client (LCU API) to automatically handle champion select: ban selection, champion pick, rune page setup, summoner spell assignment, and skin selection — all based on your saved per-role preferences.

The application runs a **FastAPI** HTTP server in a background thread and a **PyQt6** desktop GUI in the main thread.

---

## Features

- Role-based ban and champion pick (up to 3 picks per role, priority order)
- Automatic rune page creation — uses your saved custom presets or falls back to the highest win-rate page from `runes.json`
- Up to 3 custom rune presets per champion, selectable per champion slot
- Per-champion summoner spell configuration
- Skin selection (owned skins only)
- Multi-account manager with encrypted password storage and auto-login via Riot Client
- Auto-queue accept
- System tray support — minimizes to tray, toast notifications on game start
- Auto-update via GitHub Releases (optional)

---

## Requirements

- Windows 10 or 11
- League of Legends Client installed and running
- Python 3.13+ (only needed when running from source)

---

## Installation (from source)

```powershell
pip install -r requirements.txt
```

---

## Running

**Full app** (GUI + API backend):

```powershell
python run_app.py
```

**API only** (development / headless):

```powershell
python main.py
```

The FastAPI server listens on `http://127.0.0.1:8000`.

---

## Build EXE (PyInstaller)

```powershell
python -m PyInstaller --clean -y run_app.spec
```

Output: `dist/RunePilot/RunePilot.exe`

---

## Build Installer (Inno Setup)

1. Build the EXE first (see above).
2. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`ISCC.exe` must be on PATH or in its default location).
3. Run the build script:

```powershell
powershell -ExecutionPolicy Bypass -File installer\build_installer.ps1
```

Output: `dist\installer\RunePilotSetup-<version>.exe`

---

## First-time usage

1. Launch the app. The account login window opens first — add your Riot account credentials or click **Continue Without Login** if the client is already running.
2. In the main window, select your **Game Mode** and **Role Preferences**.
3. For each role tab, set a **Ban** champion and at least one **Pick** champion.
4. Click **Refresh Champions** to fetch your owned/free-to-play champion list from the running client.
5. Optionally configure **custom runes** (up to 3 presets per champion), **summoner spells**, and **skin** per champion slot.
6. Click **Start**. RunePilot will handle champion select automatically from now on.

Your settings are saved automatically and restored on the next launch.

---

## Configuration

| Item | Location |
|------|----------|
| User settings | `%APPDATA%\RunePilot\user_config.json` |
| Application log | `%APPDATA%\RunePilot\run_app.log` |
| Rune data | `runes.json` (bundled with the app) |
| LCU lockfile | Auto-detected; override with `LOL_LOCKFILE` env var |

---

## Auto-update (GitHub Releases)

RunePilot can check for updates on startup. It is disabled by default unless a repo is configured.

| Environment variable | Description |
|---|---|
| `RUNEPILOT_UPDATE_REPO` | GitHub repo to check (e.g. `owner/repo`) |
| `RUNEPILOT_GITHUB_TOKEN` | Personal access token for private repos |
| `RUNEPILOT_DISABLE_AUTO_UPDATE` | Set to `1` to disable the update check entirely |
| `RUNEPILOT_UPDATE_ASSET_PREFIX` | Installer filename prefix (default: `RunePilotSetup-`) |
| `RUNEPILOT_UPDATE_ASSET_EXT` | Installer filename extension (default: `.exe`) |

Recommended release tag format: `v1.0.0`. Recommended installer asset name: `RunePilotSetup-1.0.0.exe`.

---

## Architecture

Six-layer Clean Architecture under `src/rune_pilot/`:

```
presentation/ (PyQt6)
      |
      | HTTP (requests)
      v
composition/ (FastAPI)
      |
      v
application/ (use cases)
      |            |
      v            v
infrastructure/  domain/
(LCU, Riot,     (models,
 crypto, scraper) constants)

shared/ (used by all layers)
```

See [CLAUDE.md](CLAUDE.md) for the full developer guide.
