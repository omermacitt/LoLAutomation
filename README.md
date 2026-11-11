# RunePilot

RunePilot is a Windows automation tool for League of Legends. It uses the local
League Client API (LCU) to manage champion picks, bans, rune pages, summoner spells
and skins from your saved preferences.

## Why RunePilot exists

RunePilot started with a familiar problem: long matchmaking waits and those
moments when you need to step away from your computer briefly. If you already
know what you want to play, it can handle your configured pre-game routine while
you spend less time watching the queue and champion-select screens.

It works best when your **roles, champion preferences, rune presets and skins
are set up before you start**. If those choices are still undecided, configure
them first or make your selections manually. Be ready to return for any manual
selection handoff and to play the match. The goal is to make waiting easier;
we still want our teammates to have a good game. :D

**RunePilot currently does not choose champions or runes based on the opposing
team.** It follows your saved champion priorities and rune preferences, with
bundled recommendations available. Matchup-aware champion and rune selection
are planned for future updates.

## Current application

The project has a modern **React + TypeScript** development interface and a
**PyQt6** desktop client. Both use the same layered Python/FastAPI backend.
The planned Tauri desktop shell is not implemented yet; the React interface
currently runs in a browser during development.

## Features

- Three prioritized champion picks and one ban per role. A champion can appear
  only once in a role's pick list; different roles are independent.
- Normal Draft, Ranked Solo/Duo and Ranked Flex queue selection, with primary
  and secondary role preferences, matchmaking and ready-check acceptance while
  automation is running.
- Autofill and unavailable-pick handling: banned/taken champions are skipped in
  preference order. If no configured pick is available for the assigned role,
  selection is handed back to the player instead of choosing a random champion.
  The React interface keeps the manual-selection notice visible across pages.
- A rune editor with current client data, three saved presets per champion and
  recommendations from the bundled `runes.json` dataset.
- Summoner spells and owned/default skin selection per role and champion, with
  champion portraits and skin artwork supplied by the running League Client.
- Ordered settings saves, conflict detection between windows, explicit Start/Stop
  controls and recovery after failed requests.
- System tray support, optional Windows toast notifications and configurable
  GitHub release updates in the PyQt6 desktop client.

Rune presets and the active preset selection are currently **shared across roles
for each champion**. Role-specific rune selection is planned. Bundled rune
recommendations are not a live meta or win-rate feed.

## Requirements

- Windows 10 or 11 for the backend and desktop application.
- Python **3.11+**; the examples and Windows CI use **3.13**.
- Node.js **22.12+** for the React interface.
- League of Legends open and signed in for live catalogs and game automation.
- Microsoft Edge for the configured Playwright browser tests.

## Install from source

Run these commands in PowerShell from the repository root. Installing the `dev`
extra includes the test, lint, formatter and packaging tools.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Run the React interface

In the first terminal, start the backend from the repository root:

```powershell
.\.venv\Scripts\python.exe main.py
```

In a second terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open **<http://127.0.0.1:5173/>**. The backend listens on
**<http://127.0.0.1:8000>**. The development UI uses Vite's local API proxy;
`npm run preview` alone does not provide that proxy.

The backend must be able to write the user's AppData profile directory. A failed
catalog or settings load is shown in the interface; it does not replace saved
selections with defaults.

## Run the PyQt6 desktop client

```powershell
.\.venv\Scripts\python.exe run_app.py
```

This starts the backend and opens the desktop configuration window directly.
Use this entry point instead of a separate `main.py` process for the desktop
client. System tray and native update prompts belong to this client; the React
interface does not yet have a native desktop shell.

## Using RunePilot

1. Open Riot Client, sign in yourself and launch League of Legends.
2. Open one of the RunePilot interfaces above. Select the queue and your primary
   and secondary roles, then configure the role's picks and ban.
3. Refresh the champion list when needed. In React, the selected primary and
   secondary roles require an available pick and a known ban before Start;
   missing preferences for other roles are shown as autofill warnings.
4. Configure summoner spells, rune presets and skins. Champion, spell, skin and
   game-setting changes save automatically in React; rune forms use an explicit
   save action. Save or discard rune drafts before starting automation.
5. Click **Start** to enable automation. Saving settings alone does not start it.
   Complete any manual champion-selection handoff in League.
6. Use **Stop** when finished. The React **Save and finish session** action saves
   pending settings and confirms automation has stopped; closing a browser tab
   does not itself stop the separately running backend.

After manually changing Riot accounts, refresh the champion, rune and skin data.
Saved skins that are no longer available are retained with an unavailable notice
rather than silently replaced.

### Accounts and passwords

RunePilot does not provide account management, store Riot sign-in passwords,
perform automatic Riot login or launch Riot/League for you. These features were
removed on **10 November 2026**. The old `/accounts`, `/login-jobs` and
`/league/launch` API routes are no longer available.

On backend startup, obsolete `accounts` fields are removed from known current
and legacy profile files and their staged `.tmp` saves. Game settings are
preserved. Cleanup failures are reported as startup errors; no credential backup
is created.

## Configuration

| Item | Location or setting |
| --- | --- |
| User settings | `%APPDATA%\RunePilot\user_config.json` |
| Desktop application log | `%APPDATA%\RunePilot\run_app.log` |
| Bundled recommendation data | `runes.json` in the repository root |
| League Client lockfile | Common install paths, or `LOL_LOCKFILE` / `LOL_LOCKFILE_PATH` |

Use one backend process for the profile. Settings writes are atomic and current
clients use ETags to detect conflicting edits; separate backend processes do not
share a cross-process file lock.

## GitHub release updates

The PyQt6 client can check for updates when a repository is configured. No update
repository is configured by default.

| Environment variable | Purpose |
| --- | --- |
| `RUNEPILOT_UPDATE_REPO` | Repository to check, such as `owner/repo` |
| `RUNEPILOT_GITHUB_TOKEN` | Optional token for private releases; falls back to `GITHUB_TOKEN` |
| `RUNEPILOT_DISABLE_AUTO_UPDATE` | `1`, `true`, `yes` or `on` disables update checks |

Only newer numeric release versions are offered. Setup/installer `.exe` assets
are preferred over standalone executables. A release without an installer keeps
the browser-based release-page flow. Installer downloads require a release
registered by the backend and an HTTPS GitHub asset URL under the configured
repository. Installation requires the user's confirmation.

## Tests and code quality

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check src tests main.py run_app.py
.\.venv\Scripts\python.exe -m black --check src tests main.py run_app.py
```

For the React interface:

```powershell
cd frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
```

The Python suite uses temporary profiles and stubbed external operations; Qt
checks run offscreen. Browser tests cover desktop, compact and mobile widths.
Writes and game commands use mocked APIs. Optional live read checks need a
running backend/League Client and do not modify the real profile.

[GitHub Actions](.github/workflows/ci.yml) runs Python tests and Ruff/Black on
Windows, plus frontend unit tests and the production build on Linux. Playwright
browser tests are run separately from that workflow.

## Build the desktop executable

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean -y run_app.spec
```

The output is `dist/RunePilot/RunePilot.exe`. This packages the PyQt6 desktop
client, not the React development interface. The repository includes the
[PyInstaller specification](run_app.spec); Tauri packaging and an installer build
pipeline remain future work.

## Architecture and development notes

The Python backend lives under `src/rune_pilot/`:

| Package | Responsibility |
| --- | --- |
| `domain/` | Pure models, selection decisions and migration rules |
| `application/` | Use cases, automation lifecycle and collaborator ports |
| `infrastructure/` | LCU access, profile storage and external adapters |
| `composition/` | FastAPI routes and dependency wiring |
| `presentation/` | PyQt6 views and controllers; backend access is through HTTP |
| `shared/` | Metadata, constants and resource helpers |

The React interface lives in `frontend/` and accesses the backend over HTTP.
Architecture tests enforce the Python dependency boundaries.

- [Developer guide and layer rules](CLAUDE.md)
- [React setup and behavior details](frontend/README.md)
- [Roadmap](ROADMAP.md)
- [UI migration plan](docs/plans/ui-modernization.md)
- [UX scenarios and validation limits](docs/qa/ux-scenarios.md)
