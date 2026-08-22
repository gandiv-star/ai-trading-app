"""
Gandiv AI Trading Terminal — storage/json_store.py

Purpose
-------
Safe, atomic JSON persistence for a single file — the low-level piece
of your Phase 12 requirement (atomic write, backup, recovery,
corruption protection). storage/repository.py builds the
Portfolio-specific logic on top of this; this file only knows about
bytes/dicts, not about trading concepts at all.

What this fixes from the old code
------------------------------------
The old app wrote gandiv_data.json with a plain `open(file, "w")` +
`json.dump(...)`. If the process crashed or was killed mid-write
(very possible on a GitHub Actions runner being cancelled, or a
Streamlit Cloud container restarting), that leaves a TRUNCATED,
corrupted JSON file — and the next read fails or silently loses data.

This file writes to a temporary file first, then atomically renames
it over the real file (os.replace is atomic on both POSIX and
Windows) — so a crash mid-write leaves the OLD file untouched, never
a half-written one. It also keeps a rolling set of numbered backups,
so even a successful-but-wrong write can be rolled back manually.

What this file does NOT solve
---------------------------------
The Streamlit-Cloud-vs-GitHub-Actions DUAL WRITER problem from the
Phase 1 audit (two separate processes, two separate filesystems,
each thinking their local file is authoritative) is a DIFFERENT
problem — atomicity protects against a crash mid-write to the SAME
file; it does not create a shared file across two different hosts.
That still needs a real shared backend (the git-commit / Google
Sheets / Supabase decision you were asked about earlier). This layer
is written so that swapping in a networked backend later only means
adding a new class here — repository.py and paper/engine.py above it
would not need to change.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import datetime as dt
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_BACKUPS = 5


class CorruptionError(Exception):
    """Raised when a JSON file and ALL of its backups are unreadable."""


def atomic_write_json(path: str, data: Any) -> None:
    """
    Write `data` as JSON to `path`, atomically. On any failure, the
    original file (if any) is left completely untouched — there is no
    window where `path` contains a partial write.
    """
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())  # force to disk before the rename, not just OS buffer
        os.replace(tmp_path, path)  # atomic on POSIX and Windows
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _backup_path(path: str, index: int) -> str:
    return f"{path}.bak{index}"


def rotate_backups(path: str) -> None:
    """
    Called AFTER a successful write of `path`, to push a copy of the
    just-written file into the backup rotation (bak1 = most recent
    backup, bak{MAX_BACKUPS} = oldest kept).
    """
    if not os.path.exists(path):
        return

    oldest = _backup_path(path, MAX_BACKUPS)
    if os.path.exists(oldest):
        os.remove(oldest)

    for i in range(MAX_BACKUPS - 1, 0, -1):
        src = _backup_path(path, i)
        if os.path.exists(src):
            os.replace(src, _backup_path(path, i + 1))

    shutil.copy2(path, _backup_path(path, 1))


def save_json(path: str, data: Any) -> None:
    """
    THE public write function: rotate backups of the PREVIOUS version
    (if any), then atomically write the new version. Backups are
    rotated before the write so a backup always reflects a
    known-previously-good state, never the version currently being
    written.
    """
    if os.path.exists(path):
        rotate_backups(path)
    atomic_write_json(path, data)


def load_json(path: str) -> Optional[Any]:
    """
    THE public read function. If `path` is missing entirely, returns
    None (caller decides what "no saved state yet" means). If `path`
    exists but is corrupted (invalid JSON), automatically falls back
    to the most recent readable backup and logs a warning — never
    silently loses everything just because the LAST write was
    interrupted.

    Raises CorruptionError only if the main file AND every backup are
    all unreadable — at that point there is genuinely nothing left to
    recover automatically.
    """
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("json_store.load_json: primary file corrupted (%s) — trying backups for %s", exc, path)

    for i in range(1, MAX_BACKUPS + 1):
        backup = _backup_path(path, i)
        if not os.path.exists(backup):
            continue
        try:
            with open(backup, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.warning("json_store.load_json: recovered from backup #%d for %s", i, path)
            return data
        except (json.JSONDecodeError, OSError):
            continue

    raise CorruptionError(
        f"json_store.load_json: {path} and all {MAX_BACKUPS} backups are unreadable — "
        f"manual recovery needed."
    )
