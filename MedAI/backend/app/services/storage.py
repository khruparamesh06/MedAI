"""
Private image storage.

Files live outside any static directory and are served only through an authorized API route.
Stored names are server-generated (uuid4 hex); the user's original filename is metadata only.
"""
import re
import uuid
from pathlib import Path

from app.core.config import get_settings

_SAFE_NAME = re.compile(r"^[0-9a-f]{32}\.png$")


def storage_root() -> Path:
    root = get_settings().upload_dir
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def new_stored_name() -> str:
    return f"{uuid.uuid4().hex}.png"


def path_for(stored_name: str) -> Path:
    """Resolve a stored name to a path, refusing anything that is not a generated name."""
    if not _SAFE_NAME.fullmatch(stored_name):
        raise ValueError("Invalid stored filename")
    root = storage_root()
    path = (root / stored_name).resolve()
    if path.parent != root:  # defence in depth against path traversal
        raise ValueError("Invalid storage path")
    return path


def save(stored_name: str, data: bytes) -> Path:
    path = path_for(stored_name)
    with path.open("xb") as f:  # "x": never overwrite an existing file
        f.write(data)
    return path


def delete(stored_name: str) -> None:
    try:
        path_for(stored_name).unlink(missing_ok=True)
    except ValueError:
        pass
