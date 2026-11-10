# RunePilot — Developer Guide

## Project Overview

RunePilot is a Windows desktop automation tool for League of Legends. It auto-picks champions, applies rune pages, sets summoner spells, selects skins, and manages auto-queue. Riot/League sign-in is handled manually by the user; RunePilot does not store account credentials.

The application runs a FastAPI HTTP server in a background thread and a PyQt6 desktop GUI in the main thread. All desktop backend access uses HTTP, including automation, settings, game-data queries and updates. Presentation imports no application or infrastructure modules.

---

## How to Run

```bash
# Full app (GUI + API backend)
python run_app.py

# API only (no GUI — development / testing)
python main.py

# Tests
python -m pytest

# Build Windows EXE
python -m PyInstaller --clean -y run_app.spec
```

The FastAPI server listens on `http://127.0.0.1:8000`.

When an agent launches `main.py` from a workspace-restricted shell, the backend
needs permission to write `%APPDATA%\RunePilot`, which is outside the workspace.
Launch that backend command with the appropriate sandbox permission. A healthy
`/health` response alone does not prove settings can be saved: a restricted
process can serve the UI but return 500/PermissionError for every changed
setting, leaving the last saved game mode in place. Verify an unchanged,
conditional settings round-trip after fixing launch permissions; do not move
the user's profile or change its ACLs to work around the sandbox.

---

## Architecture

Six packages under `src/rune_pilot/`, with these dependency boundaries:

```
Runtime: presentation/api_client.py --HTTP--> FastAPI routes --> application

Python import dependencies:
presentation   --> domain, shared
application    --> domain, shared, application/ports
infrastructure --> application/ports, domain, shared
domain         --> shared (pure helpers only)
shared         --> shared
composition    --> all packages (constructs adapters and injects them into services)
```

**Layer rule**: application defines the interfaces it needs; infrastructure supplies their implementations. Composition is the only place that constructs and wires concrete backend dependencies.

- `presentation/` may import `domain/` — pure models and constants are safe to read directly. Backend I/O goes through HTTP, not application or infrastructure imports.
- `presentation/` reaches the backend only through `presentation/api_client.py`. No other UI module builds a URL or calls `requests`.
- `domain/` is pure Python — no LCU calls, no file I/O, no PyQt.
- `application/` has no direct imports of infrastructure, HTTP libraries, FastAPI or PyQt. Accept collaborators through constructor arguments.
- `shared/` contains small common helpers and metadata. Network operations belong in infrastructure.

`tests/architecture/test_dependencies.py` enforces these rules without migration exceptions. New cross-layer violations fail the test; do not add exemptions to bypass the boundaries.

---

## Layer Descriptions

| Layer | Path | Responsibility |
|-------|------|----------------|
| `shared/` | `src/rune_pilot/shared/` | App-wide constants, config paths, logging helpers, resource paths. No business logic or network access. |
| `domain/` | `src/rune_pilot/domain/` | Pure business logic. Pydantic models, game constants (rune style IDs, spell IDs, roles), ID normalization, config parsing and legacy migration. Zero I/O. |
| `infrastructure/` | `src/rune_pilot/infrastructure/` | All external I/O: LCU HTTP client (lockfile auth), Selenium scraper, rune data loader, config file read/write. |
| `application/` | `src/rune_pilot/application/` | Orchestration, use cases and ports. Automation lifecycle, config persistence, champion/skin/perk queries. |
| `presentation/` | `src/rune_pilot/presentation/` | PyQt6 UI. Split into `views/` (widgets), `controllers/` (backend and update flows), `view_models/` (shared UI state), `dialogs/`, `widgets/`. |
| `composition/` | `src/rune_pilot/composition/` | Dependency wiring and FastAPI routes. `create_app()` shares automation, settings, queries and update services across requests. |

---

## Key Files

| File | Purpose |
|------|---------|
| `run_app.py` | Main entry point — starts FastAPI thread + PyQt6 GUI |
| `src/rune_pilot/composition/api_app.py` | `create_app()` — builds FastAPI, automation and settings services; injects `ConfigRepository` |
| `src/rune_pilot/composition/endpoints.py` | Settings, game-data queries, health and automation HTTP routes |
| `src/rune_pilot/application/automation_service.py` | Owns the automation loop's lifecycle and live config |
| `src/rune_pilot/application/automation_state.py` | Versioned settings snapshots and per-invocation rune/skin progress |
| `src/rune_pilot/application/automation.py` | The loop itself (champion select, runes, spells, skins) |
| `src/rune_pilot/application/ports/league_client.py` | Named League operations and library-independent response contract |
| `src/rune_pilot/infrastructure/league_client_adapter.py` | Converts named operations to authenticated LCU requests |
| `src/rune_pilot/application/ports/rune_data.py` | Recommendation data source contract |
| `src/rune_pilot/infrastructure/rune_data_provider.py` | Lazy `JsonRuneData`, with an instance-owned cache and defensive copies |
| `src/rune_pilot/domain/champ_select.py` | Pure ban/pick availability and spell pair decisions |
| `src/rune_pilot/domain/rune_rules.py` | Pure rune recommendation selection and safe page naming |
| `src/rune_pilot/application/config_service.py` | Loads and saves `UserConfig` |
| `src/rune_pilot/application/ports/config_store.py` | Storage contract: read and atomic update |
| `src/rune_pilot/application/game_query_service.py` | UI query use cases; readers injected by composition |
| `src/rune_pilot/domain/game_data.py` | Validated HTTP contracts for champion, skin, gameflow and rune queries |
| `src/rune_pilot/infrastructure/config_repository.py` | The only reader/writer of `user_config.json` |
| `src/rune_pilot/domain/user_config.py` | `UserConfig` + every legacy config migration |
| `src/rune_pilot/domain/models.py` | `AutomationConfig` — the model passed from GUI to API |
| `src/rune_pilot/presentation/main_window.py` | Main window — assembly and wiring only |
| `src/rune_pilot/presentation/views/role_tab.py` | One role's ban and three champion rows |
| `src/rune_pilot/presentation/view_models/selection_model.py` | Rune/skin/spell state shared across role tabs |
| `src/rune_pilot/presentation/api_client.py` | The only place the UI knows the backend's URL |
| `src/rune_pilot/presentation/controllers/settings_controller.py` | Background startup load, ordered/debounced saves, retries and asynchronous close flush |
| `src/rune_pilot/presentation/controllers/background_query.py` | One background read per query; delivers results on the Qt thread and ignores results after close |
| `src/rune_pilot/presentation/controllers/rune_data_controller.py` | One catalog for three editors; deduplicated background icon queue |
| `src/rune_pilot/application/update_service.py` | Registered update offers and serialized/reusable downloads |
| `src/rune_pilot/application/ports/update_source.py` | Release discovery and installer download contract |
| `src/rune_pilot/infrastructure/github_updates.py` | GitHub requests and isolated local installer storage |
| `src/rune_pilot/composition/update_endpoints.py` | Update discovery and installer download routes |
| `src/rune_pilot/presentation/controllers/update_controller.py` | Background HTTP update requests, suppressing results after close |

---

## Configuration & Data

| Item | Location |
|------|----------|
| User config | `%APPDATA%\RunePilot\user_config.json` |
| App log | `%APPDATA%\RunePilot\run_app.log` |
| Rune data | `runes.json` in project root (bundled via PyInstaller spec) |
| LCU lockfile | Auto-detected; override with `LOL_LOCKFILE` env var |

`ConfigRepository` is the only reader/writer of profile files. Settings updates lock, re-read, merge and write atomically. Unrelated preference fields survive; obsolete `accounts` data is deliberately removed.

`GET /settings` returns only `UserConfig` fields, after legacy migration. `PUT /settings` replaces the settings fields and preserves unrelated preference keys and removes obsolete accounts; a failed write returns HTTP 500. The UI disables settings edits and Start until the initial load succeeds, retries when the backend starts late, and never saves defaults after a failed HTTP load. Writes run sequentially on worker threads, coalesce edits, and retry the latest snapshot. Refresh preserves local selections without reloading stale server data. Window/tray close waits asynchronously for the final save; a failed close save leaves the window open with an error.

If the champion list could not be loaded, edits/Start remain disabled and close does not write empty selections. Refresh Champions stays available after settings load and restores the loaded selections once the League Client responds.

`GET/PUT /settings` include an ETag for normalized settings only (unrelated preference changes do not affect it). Conditional saves compare `If-Match` inside the repository mutation and return 412 without writing if another window changed settings. Requests without `If-Match` remain compatible with older clients. Current Qt and React API clients retain the revision and reconcile uncertain save replies before retrying. React writes require the revision; never bypass a conflict with an unconditional retry or advance the revision without reconciling local edits.

Champion preferences must be unique within each role; reuse across roles is allowed and bans are separate. `UserConfig.from_raw()` migrates old duplicates by keeping the first occurrence and replacing later occurrences with `None`, preserving slot positions and per-champion customization. Reads do not rewrite the file. `ConfigService.save()` rejects duplicate choices before touching storage; `AutomationConfig` and the automation service also enforce uniqueness. The React grid disables champions used in another slot of the active role; the selection model independently guards stale clicks. Clearing a preference releases its champion for other slots.

## Game Data HTTP Queries

| Endpoint | Contract |
|----------|----------|
| `GET /champion-catalog` | Sorted all-champion ban options and owned/free-to-play pick options |
| `GET /champions/{champion_id}/portrait` | Cached PNG for a known regular champion; 404 when missing, 503 when LCU is unavailable |
| `GET /gameflow` | Current phase; `null` when the League Client is unavailable |
| `GET /champions/{champion_id}/skins` | Default skin followed by owned skins for this champion |
| `GET /champions/{champion_id}/skins/{skin_id}/artwork` | Known skin's metadata-backed local JPEG/PNG; bounded cache; missing artwork 404, unavailable source 503 |
| `GET /runes/catalog` | Rune styles and perks, retaining legacy LCU shape support |
| `GET /runes/icons/{perk_id}` | Binary PNG bytes for a known perk icon; 404 when unavailable |

`create_app()` wires one `LeagueClient` into `ChampionQuery`, `PerkQuery`, `SkinQuery`, `LobbyService` and `AutomationRunner`, and a `RuneDataSource` into `RuneService`. Production uses `LcuLeagueClient` and `JsonRuneData`; tests can inject both without a running client. `GameQueryService` receives bound query methods. Champion and perk metadata caches belong to the query instances and are guarded by locks. LCU URLs and request payload mapping belong to infrastructure; application uses named operations. Catalog/ownership failures return 503, not a successful empty response or an offer to pick every champion. The old `/champions` endpoint remains compatible.

Supported queues use the regular roster. LCU also lists League Classic `Jade_` variants with identical localized names and distinct IDs (for example Aatrox 266 / Jade_Aatrox 60266). `domain.champion_service.is_mode_champion_variant()` filters these by alias in catalog, legacy owned-list and name/slug queries. Do not deduplicate display names, assume a numeric ID ceiling, transfer variant ownership to the regular champion, or rewrite saved IDs. Riot documents separate Classic data in [mode-specific content](https://developer.riotgames.com/docs/lol#data-dragon_mode-specific-content).

`ChampionPortraitQuery` is wired separately into `app.state.champion_portraits` and uses the existing `LeagueClient.asset` port. Only a normal champion's exact metadata-provided square portrait path is accepted. PNG bytes are checked and cached for five minutes, at most 256 entries / 1 MiB per image; failed reads are retryable. HTTP success is privately cacheable for five minutes; missing portraits use no-store. Frontend image URLs stay in `frontend/src/api/client.ts`. `ChampionArtwork` lazily loads grid portraits and retains initials on failure; Refresh retries failures. The champion grid measures its CSS card minimum/content width and shows three full rows per page, with the last page allowed to be incomplete. Resizing preserves the previous page anchor without changing saved selections.

All desktop query I/O runs through `ApiClient` and `BackgroundQuery` on worker threads. Requests of the same type do not overlap. LCU calls have a 2-second connect/read timeout; client catalog reads allow 15 seconds for multi-request lookups. A failed refresh leaves the current selections intact. A successful refresh preserves edits made while the request was running; saved champions that are no longer owned remain as disabled unavailable entries, preserving their IDs. Settings and champion catalogs can arrive in either order.

Skin results are ignored if the target row changed champions. Rune presets share one catalog load, disable editing/saving until it succeeds, and offer Retry on failure. Icons are optional, fetched once per perk per dialog in a background queue, and decorate existing combo items without rebuilding selections. Closing a window/dialog suppresses late results.

The React skin gallery uses the existing owned/default skin query and stores choices per role/champion through the shared settings writer. It preserves saved unavailable IDs, disables choices on query errors, and ignores abandoned champion responses. Images use `SkinArtworkQuery`, known skin IDs and exact metadata-provided League character asset paths; no caller URLs are accepted. JPEG/PNG bytes are limited to 3 MiB per image, 32 MiB total and 32 cached images for five minutes; metadata is bounded to 32 champions. Lazy card images fall back to portraits without resetting selection. Gallery writes never start automation; acknowledged settings use the existing update-only flow.

React buttons that swap loading icons must isolate the icon and label in stable
elements (`<span>{icon}</span><span>{label}</span>`). Browser translation can
replace bare text nodes, causing React `insertBefore`/`removeChild` errors when
adjacent icons change. The rune-save browser regression deliberately wraps text
in `<font>` while validation is pending, then confirms the editor survives the
successful save. Do not patch global DOM methods or swallow placement errors.
`AppErrorBoundary` supplies an explicit reload screen for unexpected render
failures; reload may lose unsaved edits and does not stop backend automation.

## Manual Riot sign-in and removed account support

Account management and automatic Riot login were removed on 10 November 2026 at the user's request. Do not restore account forms, saved passwords, credential encryption, Riot login automation or the old `/accounts`, `/login-jobs` and `/league/launch` HTTP routes. Both Qt and React open configuration directly. The user opens Riot Client, signs in and launches League themselves; Refresh reloads League data after a manual account change.

Production backend lifespan calls `ConfigRepository.remove_legacy_accounts()` before serving requests. It atomically removes only `accounts` from every known current/legacy profile and their `.tmp` saves, preserving all other JSON fields and creating no credential backup. Unreadable data or failed writes abort startup with an explicit migration error. Repository reads suppress obsolete accounts and writes strip them to prevent reintroduction by stale settings. Native Riot sign-in/crypto adapters and their exclusive dependencies are gone. LCU's transient client lockfile authentication remains necessary for game automation; it is not a saved Riot login password.

Tests isolate default profiles in temporary directories before app startup. Never use real user profiles for migration tests or log stored account fields.

## Automation Lifecycle

`AutomationService` owns settings and a monotonic revision. Settings inputs, reads and worker snapshots are deep copies; runtime progress never enters settings or HTTP responses. Every Start/update advances the revision, including unchanged settings. `AutomationRunner` owns progress for one invocation, resets it on revision changes and absent champion-select sessions, and tracks rune application by champion. Failed rune/skin writes retry; skin success requires a successful LCU response.

Stop cancels that invocation's event permanently and wakes its waits. A Start during pending Stop queues a fresh invocation on the same worker after the old loop returns; it cannot revive the old signal or run two automation loops concurrently. Stop is nonblocking and an in-flight LCU request can finish. Side effects check cancellation between calls. Unexpected loop exit clears running status. `shutdown()` rejects future starts, cancels the worker and waits up to 10 seconds, returning whether it finished. FastAPI lifespan invokes shutdown; the desktop entry point requests graceful server shutdown after Qt exits. Minimize-to-tray keeps the desktop and backend alive.

`PUT /automation/config` calls `update_running()` under the worker lock. It updates the current settings snapshot/revision only while running and returns 409 otherwise; it never creates or revives a worker. React uses it for acknowledged live settings updates. Only an explicit Start uses `/start_automation`.

`SelectionFeedback` is a shared, thread-safe application store, injected via the
runner and exposed as optional `/health.selection` only while running. It is
transient and never enters settings. Empty assigned-role pools, exhausted choices
and failed picks latch manual control to the game/action; revisions do not revoke
it. Own hovers/locked champions are respected and future `isInProgress=false`
actions cannot be locked. Session exit clears the latch. Confirmed manual picks
continue rune/skin/spell application for the actual champion. First-preference
derived spell defaults cannot be applied to a replacement champion; older generic
spell-only API configs remain supported. Role-specific rune selection is still
pending: existing champion-shared rune presets remain compatible.

React requires pick/ban coverage only for the chosen primary/secondary roles
(all roles if neither is selected), and warns about other autofill gaps. It polls
health every second while running, every four seconds otherwise. `SelectionAlert`
stays visible across views without covering navigation, deduplicates audio, guards
delayed playback after mute/Stop and retains a known notice on read failure. Browser
audio restrictions have a visible fallback and an explicit retry; no game commands
are triggered by notification display.

## Update HTTP Flow

`GET /updates` returns `{ "update": null }` when disabled, unavailable, or on the installed release tag; otherwise it returns `UpdateInfo` with a backend-issued `update_id`. The legacy release-tag comparison policy is retained. `POST /updates/{update_id}/download` accepts only an offer discovered by this backend and returns an absolute `installer_path` on the same machine as the desktop. It accepts no client URL or destination. Unknown/expired offers return 404; download failures return a sanitized 502. Offers are process-local, deduplicated, and limited to eight. Successful downloads are reused for retries within that offer's lifetime.

Composition reads `RUNEPILOT_DISABLE_AUTO_UPDATE`, `RUNEPILOT_UPDATE_REPO` (default `UPDATE_REPO_DEFAULT`), and `RUNEPILOT_GITHUB_TOKEN`/`GITHUB_TOKEN`. Tokens stay in the backend adapter. GitHub checks have a 4-second timeout; streaming downloads have a 300-second timeout and the desktop HTTP download allows 310 seconds. Installers use a fresh temporary directory; only HTTPS GitHub release assets from the configured repository and plain `.exe` filenames are accepted. Failed/empty downloads remove their partial files. Successful files remain available for the installer to run.

`UpdateController` schedules one startup check after 1.5 seconds, remains silent on check failures, and performs download requests on a worker thread. It prevents duplicate UI downloads, reports failures, and suppresses late results after window close. A release without an installer retains the browser flow. The existing confirmation dialog authorizes installer launch; tests never launch installers or contact GitHub.

---

## Dev Workflow

For user-facing behavior changes, request an independent UX review agent using
[.agents/ux-tester.md](.agents/ux-tester.md). The user requested a dedicated agent
that acts as an ordinary player, writes scenarios and validates usability. Give
it a separate review scope; product changes stay with the implementing agent.
Use mocked writes/game actions and report untested real-match behavior explicitly.
Scenario coverage and evidence live in [docs/qa/ux-scenarios.md](docs/qa/ux-scenarios.md).

**Adding a new automation feature:**
1. Put pure decisions in `domain/`; orchestrate them in `application/automation.py`
2. If it needs GUI control, add an endpoint in `composition/endpoints.py`
3. Add the UI control in `presentation/` and a method on `presentation/api_client.py`
4. The GUI calls the endpoint through `ApiClient` — never by importing application code
5. Add external operations to an application port, implement them in infrastructure, and wire them in composition

**Adding a new LCU query used by the UI:**
1. Define the needed port and query/use case in `application/`; implement external I/O in `infrastructure/` and wire it in composition
2. Expose an endpoint and add an `ApiClient` method
3. Call it from a presentation controller on a worker thread; deliver results through Qt signals

**Adding a persisted setting:**
1. Add the field to `domain/user_config.py` and to `OWNED_KEYS`
2. Handle any legacy shape in `UserConfig.from_raw()`, and cover it in `tests/domain/test_user_config.py`
3. Include it in `MainWindow._current_config()` / `_apply_config()`; settings already travel through `/settings`


---

## Tests

`python -m pytest` covers domain/config migration, removed-account cleanup, atomic settings persistence, absent credential endpoints, automation lifecycle, architecture imports, HTTP contracts, lost-response recovery, query timeouts, and asynchronous controller/window/dialog behavior. Tests use temporary profiles and stub external queries; Qt runs with `QT_QPA_PLATFORM=offscreen`. Tests never migrate real user profiles or perform Riot sign-in.

Install test dependencies with `pip install -e .[dev]` (including `pytest` and `httpx`). When changing presentation, maintain offscreen assembly checks and cover asynchronous failure/ordering behavior where data loss is possible.

---

## Known Architectural Debt

Future feature ideas and deferred scope are tracked in [ROADMAP.md](ROADMAP.md).
The React/TypeScript/Tauri UI migration is tracked in [docs/plans/ui-modernization.md](docs/plans/ui-modernization.md). The default desktop runtime remains Qt; keep its entry until the migration acceptance gates pass.
The React development UI lives in `frontend/`; see [frontend/README.md](frontend/README.md). Champion/ban ordering, spells, queue/role preferences, sequential autosave and automation controls are implemented. The loopback Vite proxy allowlists paths/methods and checks origin plus an in-memory session token for writes. Frontend HTTP stays in `frontend/src/api/client.ts`; backend owns config migration and game rules. Start flushes settings, Stop invalidates pending starts/updates, and live updates use the update-only endpoint. Controlled session finish flushes and confirms Stop; direct browser close can only request a beforeunload warning. The rune editor now includes three champion-shared presets, catalog-backed validation, explicit save/delete/selection, retained local drafts and read-only bundled recommendations. Rune forms must be saved or discarded before Start/controlled finish. Read-only editor APIs are `/runes/editor-catalog`, `/champions/{id}/runes/recommended` and `/runes/icons/{id}`; `POST /runes/validate` validates without game writes. New rules live in `domain/rune_editor.py`, orchestration in `application/rune_editor_service.py`, and React UI in `frontend/src/features/runes/`. Shard repeats across permitted rows are legal. Legacy raw catalog and Qt dialogs remain compatible. The skin gallery is implemented in `frontend/src/features/skins/` with owned/default cards, role-specific selection, search and optional League artwork. The Tauri runtime remains pending. Account management was removed by product decision.
The mobile League companion is deferred; do not treat it as active implementation work.

- **`presentation/dialogs/runes_dialog.py`** still combines rune editing widgets and selection helpers and has not been split.
- **Selenium scraper** (`infrastructure/scraper.py`) hardcodes OP.GG XPaths, which break when OP.GG changes layout. Dev-time tool only, not bundled in the EXE.
- **`win10toast` is unmaintained** and imports `pkg_resources`, removed in setuptools 81+. `presentation/notifications.py` degrades to no-op toasts rather than failing to start; install `setuptools<81` if you want toasts back.
