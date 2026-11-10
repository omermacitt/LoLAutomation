"""
Reads and writes `user_config.json`.

This is the only module that touches that file. Settings writers share a path lock
and merge their changes atomically. Removed account records are never exposed or
written; startup also purges them from current/legacy files and staged saves.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable
from typing import Any

from rune_pilot.shared.app_meta import LEGACY_CONFIG_FILE
from rune_pilot.shared.config import CONFIG_FILE, LEGACY_APP_CONFIG_FILE

# One lock per config path, shared by every repository instance pointing at that path.
# Independently constructed settings services must share the same lock.
_PATH_LOCKS: dict[str, threading.RLock] = {}
_PATH_LOCKS_GUARD = threading.Lock()


def _lock_for(path: str) -> threading.RLock:
    key = os.path.normcase(os.path.abspath(path)) if path else ""
    with _PATH_LOCKS_GUARD:
        lock = _PATH_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _PATH_LOCKS[key] = lock
        return lock


class ConfigRepository:
    """Atomic, lock-guarded access to the user config file."""

    def __init__(
        self,
        path: str | None = None,
        fallback_paths: tuple[str, ...] | None = None,
    ) -> None:
        self.path = CONFIG_FILE if path is None else path
        # Older builds wrote to a different app directory. They are read if the current
        # path has no file yet. Normal saves migrate forward; credential cleanup
        # additionally sanitizes these older files in place.
        self.fallback_paths = (
            fallback_paths
            if fallback_paths is not None
            else (LEGACY_APP_CONFIG_FILE, LEGACY_CONFIG_FILE)
        )
        self._lock = _lock_for(self.path)

    def resolve_read_path(self) -> str | None:
        """The newest config file that exists, or None when there is nothing to read."""
        for candidate in (self.path, *self.fallback_paths):
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def resolve_write_path(self) -> str | None:
        """
        The path a save should write to, with its directory created.

        Falls back to the legacy location only if the current one cannot be created —
        a read-only or missing %APPDATA% should not cost the user their settings.
        """
        for candidate in (self.path, *self.fallback_paths):
            if not candidate:
                continue
            try:
                parent = os.path.dirname(candidate)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                return candidate
            except OSError:
                continue
        return None

    def read(self) -> dict[str, Any]:
        """Settings and unrelated keys, excluding removed saved accounts."""
        with self._lock:
            data = self._read_unlocked()
            data.pop("accounts", None)
            return data

    def remove_legacy_accounts(self) -> bool:
        """Purge only account records, without backups containing credentials.

        Every known profile and its staged save is checked, including legacy
        fallback files even when the current profile already exists. Unreadable
        or malformed data is left intact and reported as a failed migration.
        """
        success = True
        seen: set[str] = set()
        for profile in (self.path, *self.fallback_paths):
            if not profile:
                continue
            for candidate in (profile, f"{profile}.tmp"):
                key = os.path.normcase(os.path.abspath(candidate))
                if key in seen:
                    continue
                seen.add(key)
                with _lock_for(candidate):
                    try:
                        with open(candidate, encoding="utf-8") as stream:
                            data = json.load(stream)
                    except FileNotFoundError:
                        continue
                    except (OSError, ValueError):
                        success = False
                        continue
                    if not isinstance(data, dict):
                        success = False
                        continue
                    if "accounts" not in data:
                        continue
                    del data["accounts"]
                    staged: str | None = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            mode="w",
                            encoding="utf-8",
                            dir=os.path.dirname(os.path.abspath(candidate)),
                            prefix=".profile-cleanup-",
                            suffix=".tmp",
                            delete=False,
                        ) as stream:
                            staged = stream.name
                            json.dump(data, stream, indent=2, ensure_ascii=False)
                        os.replace(staged, candidate)
                        staged = None
                    except (OSError, TypeError, ValueError):
                        success = False
                    finally:
                        if staged is not None:
                            try:
                                os.remove(staged)
                            except OSError:
                                success = False
        return success

    def _read_unlocked(self) -> dict[str, Any]:
        path = self.resolve_read_path()
        if not path:
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            # A corrupt file must not take the app down, but silently continuing from
            # {} would let the next save overwrite it, so say so loudly.
            print(f"[CONFIG] Could not read {path}: {e}")
            return {}
        return data if isinstance(data, dict) else {}

    def update(self, mutate: Callable[[dict[str, Any]], None]) -> bool:
        """
        Applies `mutate` to the current config and writes the result atomically.

        The read, the mutation and the write all happen under one lock, so a concurrent
        `update()` from another owner of the file can neither read stale data nor have
        its keys dropped. `mutate` must change only the keys its caller owns.
        """
        with self._lock:
            data = self._read_unlocked()
            try:
                mutate(data)
            except Exception as e:
                print(f"[CONFIG] Update aborted, file left unchanged: {e}")
                return False
            return self._write_unlocked(data)

    def _write_unlocked(self, data: dict[str, Any]) -> bool:
        path = self.resolve_write_path()
        if not path:
            print("[CONFIG] Save failed: no writable config path")
            return False

        # Never let stale callers or foreign data restore removed credentials.
        data.pop("accounts", None)
        # A staged write preserves the existing settings if serialization fails.
        tmp_path = f"{path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, path)
            return True
        except (OSError, TypeError, ValueError) as e:
            print(f"[CONFIG] Save failed: {e}")
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            return False
