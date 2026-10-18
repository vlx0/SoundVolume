"""
config.py
=========
Загрузка и сохранение пользовательских настроек SoundVolume в JSON.

Сценарий — «с какого времени по какое держать уровень громкости в N%».
Может переходить через полночь (например, 22:00 → 07:00 → 0%).
"""

import json
import os
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict


DEFAULT_SCENARIO_DAY = (8, 0, 22, 0, 70)    # 08:00 → 22:00, 70%
DEFAULT_SCENARIO_NIGHT = (22, 0, 8, 0, 0)  # 22:00 → 08:00, 0% (mute)


@dataclass
class Scenario:
    """
    Один сценарий: с какого времени по какое держать указанный уровень громкости.
    Может переходить через полночь.
    """
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    level: int  # 0..100 (0 = mute)
    enabled: bool = True

    def __post_init__(self) -> None:
        self.start_hour = max(0, min(23, int(self.start_hour)))
        self.start_minute = max(0, min(59, int(self.start_minute)))
        self.end_hour = max(0, min(23, int(self.end_hour)))
        self.end_minute = max(0, min(59, int(self.end_minute)))
        self.level = max(0, min(100, int(self.level)))
        self.enabled = bool(self.enabled)

    def crosses_midnight(self) -> bool:
        return (self.end_hour, self.end_minute) <= (self.start_hour, self.start_minute)

    def start_str(self) -> str:
        return f"{self.start_hour:02d}:{self.start_minute:02d}"

    def end_str(self) -> str:
        return f"{self.end_hour:02d}:{self.end_minute:02d}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Scenario":
        known = set(cls.__dataclass_fields__.keys())
        defaults = {f: 0 for f in cls.__dataclass_fields__ if f != "level"}
        defaults["level"] = 50
        defaults["enabled"] = True
        return cls(**{**defaults, **{k: v for k, v in d.items() if k in known}})


@dataclass
class Config:
    scenarios: list[Scenario] = field(default_factory=list)
    auto_start: bool = True
    # Принудительно держать этот уровень (выше сценариев). None = авто.
    force_level: int | None = None
    # "known_muted" — последнее состояние mute, которое мы установили.
    # Нужно потому что прочитать текущий mute через keybd_event нельзя.
    known_muted: bool = False
    # Lock для UI ↔ scheduler
    _lock: threading.RLock = field(
        default_factory=threading.RLock, repr=False, compare=False
    )

    def active_scenarios(self) -> list[Scenario]:
        with self._lock:
            return [s for s in self.scenarios if s.enabled]

    def add_scenario(self, scenario: Scenario | None = None) -> Scenario:
        with self._lock:
            if scenario is None:
                scenario = Scenario(*DEFAULT_SCENARIO_DAY, enabled=True)
            self.scenarios.append(scenario)
            return scenario

    def remove_scenario(self, index: int) -> None:
        with self._lock:
            if 0 <= index < len(self.scenarios):
                del self.scenarios[index]

    def snapshot(self) -> list[Scenario]:
        with self._lock:
            return list(self.scenarios)

    @classmethod
    def create_default(cls) -> "Config":
        return cls(
            scenarios=[
                Scenario(*DEFAULT_SCENARIO_DAY, enabled=True),
                Scenario(*DEFAULT_SCENARIO_NIGHT, enabled=True),
            ],
            auto_start=True,
        )

    @classmethod
    def load(cls, path: Path) -> "Config":
        if not path.exists():
            return cls.create_default()
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            scenarios = [Scenario.from_dict(s) for s in raw.get("scenarios", [])]
            if not scenarios:
                return cls.create_default()
            fl = raw.get("force_level")
            if fl is not None:
                try:
                    fl = max(0, min(100, int(fl)))
                except (TypeError, ValueError):
                    fl = None
            return cls(
                scenarios=scenarios,
                auto_start=bool(raw.get("auto_start", True)),
                force_level=fl,
                known_muted=bool(raw.get("known_muted", False)),
            )
        except (json.JSONDecodeError, TypeError, ValueError, KeyError):
            return cls.create_default()

    def save(self, path: Path) -> None:
        data = {
            "scenarios": [s.to_dict() for s in self.scenarios],
            "auto_start": self.auto_start,
            "force_level": self.force_level,
            "known_muted": self.known_muted,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def config_path() -> Path:
    base = Path(os.path.dirname(os.path.abspath(__file__)))
    return base / "config.json"