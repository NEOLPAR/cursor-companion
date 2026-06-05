from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .paths import CONFIG_DIR, CONFIG_FILE


@dataclass
class AppConfig:
    active_pet_id: str | None = None
    scale: float = 0.35
    offset_x: int = 22
    offset_y: int = 18
    autostart: bool = False
    visible: bool = True
    wander_when_idle: bool = False


class ConfigStore:
    def __init__(self) -> None:
        self.config = AppConfig()
        self.load()

    def load(self) -> AppConfig:
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                allowed = {field: data[field] for field in AppConfig.__dataclass_fields__ if field in data}
                self.config = AppConfig(**allowed)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                self.config = AppConfig()
        return self.config

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self.config), indent=2) + "\n", encoding="utf-8")
