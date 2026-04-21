from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_text_lossy(path: Path) -> dict[str, Any] | list[Any]:
    """Load JSON from a path, tolerating non-UTF8 bytes via replacement decode."""
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    return json.loads(text)
