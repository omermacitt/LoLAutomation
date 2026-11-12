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

The modern **React + TypeScript** interface now runs in a **Tauri 2 Windows
desktop shell**, with a bundled Python/FastAPI backend. A versioned NSIS installer
can be built locally. The first beta still needs clean-machine, old-version
migration and real League acceptance before public release. The **PyQt6** entry
remains available as a development fallback.

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
client. System tray and legacy update prompts belong to this fallback client.

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

The native client checks for updates at startup and offers an **Update** action.
Signed release builds download and verify the complete installer, save pending
settings, confirm automation has stopped, and replace the previous application's
recorded program files. Game settings and unrelated user files are preserved.
Download, signature, settings or Stop failures prevent installation.

Stable and beta releases have separate manifest feeds. Published Qt v0.0.2 clients
discover stable GitHub releases; the first transition therefore needs a published
stable/latest release with a `RunePilotSetup-<version>-x64.exe` asset. Their
existing update button can launch that Setup. Native beta.1 builds distributed
without an updater need a one-time new Setup installation.

Signing keys and release acceptance must be configured before publishing; an
unsigned local build does not receive updates. See the
[update build and signing guide](frontend/README.md#tam-paket-güncellemeleri).

The retained PyQt6 fallback uses `omermacitt/LoLAutomation` by default and supports
these backend environment settings:

| Environment variable | Purpose |
| --- | --- |
| `RUNEPILOT_UPDATE_REPO` | Repository to check, such as `owner/repo` |
| `RUNEPILOT_GITHUB_TOKEN` | Optional token for private releases; falls back to `GITHUB_TOKEN` |
| `RUNEPILOT_DISABLE_AUTO_UPDATE` | `1`, `true`, `yes` or `on` disables update checks |

Only newer release versions are offered, including prerelease precedence. Setup/installer `.exe` assets
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

## Build the Windows desktop installer

Windows x64 build prerequisites: Python 3.13.3, Node 22.15.1, Rust 1.99.1,
Visual Studio 2022 C++ Build Tools and WebView2. Install the pinned dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build-windows.lock
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
npm.cmd ci --prefix frontend
.\tools\build_desktop.ps1
```

Output: `dist/desktop/1.0.0/RunePilotSetup-1.0.0-x64.exe`,
`SHA256SUMS.txt` and `build-manifest.json`. End users need the Setup file;
Python, Node and this repository are bundled or unnecessary. WebView2 is installed
by the bootstrapper if missing, which requires Internet access.

The native host owns a private backend process and port, keeps its access key out
of the webview and stops the process on exit. Window close waits for settings and
confirmed Stop; minimize keeps the application running. Native restart retains
drafts and requires an explicit Start. Sign in to Riot and open League manually.

The version source is `src/rune_pilot/shared/app_meta.py`. After editing it, run
`python tools/release_version.py --sync`; the build rejects mismatched manifests.
[Windows beta workflow](.github/workflows/release.yml) checks tags, tests and builds
the installer, then creates a **draft** release. It never publishes on a main push.
Signed update builds additionally produce `.exe.sig` and `latest.json`; use
`tools/build_desktop.ps1 -SignedUpdates` with the documented signing environment.
The complete Setup signature, public key and version are verified before export.
The release workflow tests old Inno and previous native migration on its
disposable Windows runner. These checks must pass before publication.
Windows Authenticode signing is separate from update signing and is not configured.
Clean Windows installation, v0.0.2 migration and real League acceptance remain
pending. Keep this build as a preview until those checks are complete.

To build the retained Qt fallback instead:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean -y run_app.spec
```

The fallback output is `dist/RunePilot/RunePilot.exe` from [run_app.spec](run_app.spec).

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
