from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
from json import dumps, loads
from typing import Any


def normalise(value: Any) -> Any:
    if is_dataclass(value):
        return normalise(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): normalise(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [normalise(item) for item in value]
    return value


def to_json(value: Any) -> str:
    return dumps(normalise(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def from_json(value: str) -> dict[str, Any]:
    loaded = loads(value)
    if not isinstance(loaded, dict):
        return {"value": loaded}
    return loaded


def stable_hash(value: Any) -> str:
    return sha256(to_json(value).encode("utf-8")).hexdigest()


def redact_private_fields(value: dict[str, Any]) -> dict[str, Any]:
    blocked = {
        "api_key",
        "token",
        "secret",
        "checkpoint",
        "checkpoint_path",
        "weight_path",
        "data_root",
        "dataset_root",
        "private_config_ref",
    }
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        lower = key.lower()
        if lower in blocked or any(marker in lower for marker in ("password", "credential", "secret")):
            redacted[key] = "<redacted>"
        elif isinstance(item, dict):
            redacted[key] = redact_private_fields(item)
        else:
            redacted[key] = item
    return redacted
