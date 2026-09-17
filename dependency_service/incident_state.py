from enum import Enum


class IncidentMode(str, Enum):
    NORMAL = "normal"
    LATENCY = "latency"
    ERROR = "error"


_current_mode = IncidentMode.NORMAL


def get_incident_mode() -> IncidentMode:
    return _current_mode


def set_incident_mode(mode: IncidentMode) -> None:
    global _current_mode
    _current_mode = mode