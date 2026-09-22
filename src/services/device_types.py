"""Runtime capability defaults for smart-home device kinds."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_DEFAULT_CAPABILITIES: dict[str, dict[str, Any]] = {
    "light": {
        "actions": ["on", "off", "toggle", "set"],
        "set_fields": {
            "brightness": {"type": "integer", "minimum": 0, "maximum": 100},
            "power": {"type": "boolean"},
        },
        "requires_approval": [],
    },
    "fan": {
        "actions": ["on", "off", "toggle", "set"],
        "set_fields": {
            "speed": {"type": "integer", "minimum": 0, "maximum": 100},
            "power": {"type": "boolean"},
        },
        "requires_approval": [],
    },
    "aircon": {
        "actions": ["on", "off", "toggle", "set"],
        "set_fields": {
            "target_temperature": {"type": "number", "minimum": 16, "maximum": 30},
            "mode": {"type": "string", "enum": ["auto", "cool", "dry", "fan"]},
            "power": {"type": "boolean"},
        },
        "requires_approval": [],
    },
    "blind": {
        "actions": ["open", "close", "on", "off", "toggle", "set"],
        "set_fields": {
            "position": {"type": "integer", "minimum": 0, "maximum": 100},
            "power": {"type": "boolean"},
        },
        "requires_approval": [],
    },
    "speaker": {
        "actions": ["on", "off", "toggle", "set", "play", "pause", "stop"],
        "set_fields": {
            "volume": {"type": "integer", "minimum": 0, "maximum": 100},
            "playing": {"type": "boolean"},
            "power": {"type": "boolean"},
        },
        "requires_approval": [],
    },
    "lock": {
        "actions": ["lock", "unlock"],
        "set_fields": {},
        "requires_approval": ["unlock"],
    },
    "sensor": {"actions": [], "set_fields": {}, "requires_approval": []},
    "display": {
        "actions": ["on", "off", "toggle", "set"],
        "set_fields": {
            "text": {"type": "string", "max_length": 500},
            "message": {"type": "string", "max_length": 500},
            "power": {"type": "boolean"},
        },
        "requires_approval": [],
    },
}


def default_capabilities(kind: str) -> dict[str, Any]:
    """Return a copy of the default capability contract for a kind."""
    return deepcopy(_DEFAULT_CAPABILITIES.get(kind, {"actions": [], "set_fields": {}, "requires_approval": []}))


def known_kinds() -> tuple[str, ...]:
    """Return configured device kinds."""
    return tuple(sorted(_DEFAULT_CAPABILITIES))
