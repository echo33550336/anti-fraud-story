"""Cached, validated loader for the story configuration."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .schemas import validate_config

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "story_15nodes.json"
_CACHE: Dict[str, Tuple[Tuple[int, int], Dict[str, Any]]] = {}
_LOCK = threading.RLock()


class ConfigLoadError(ValueError):
    pass


def clear_config_cache(path: Optional[str] = None) -> None:
    """Clear one cached file or the whole in-process cache."""
    with _LOCK:
        if path is None:
            _CACHE.clear()
        else:
            key = str(Path(path).expanduser().resolve())
            _CACHE.pop(key, None)


def load_config(path: Optional[str] = None, force_reload: bool = False) -> Dict[str, Any]:
    """Load and validate JSON once, then reuse the parsed object.

    The default config is kept until explicitly reloaded. Callers should treat
    the returned dictionary as read-only.
    """
    is_default = path is None
    target = DEFAULT_CONFIG_PATH if is_default else Path(path).expanduser()
    target = target.resolve()
    key = str(target)

    with _LOCK:
        cached = _CACHE.get(key)
        if is_default and cached is not None and not force_reload:
            return cached[1]

        try:
            stat = target.stat()
        except OSError as exc:
            raise ConfigLoadError("cannot read story config %s: %s" % (target, exc))

        signature = (stat.st_mtime_ns, stat.st_size)
        if cached is not None and cached[0] == signature and not force_reload:
            return cached[1]

        try:
            with target.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise ConfigLoadError("invalid story config %s: %s" % (target, exc))

        errors = validate_config(data)
        if errors:
            raise ConfigLoadError(
                "story config validation failed: " + "; ".join(errors)
            )

        _CACHE[key] = (signature, data)
        return data
