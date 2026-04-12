from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import APP_NAME


def get_config_path() -> Path:
    if getattr(sys, "frozen", False):
        appdata_root = Path(os.getenv("APPDATA") or str(Path.home()))
        return appdata_root / APP_NAME / "config.json"
    return Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class AppConfig:
    window_geometry: str = "1380x860"
    last_left_path: str = ""
    last_right_path: str = ""
    last_directory: str = ""
    last_export_directory: str = ""
    filter_value: str = "Todos"
    search_text: str = ""
    theme: str = "Oscuro"
    restore_last_session: bool = True
    auto_compare_on_load: bool = False
    default_export_format: str = "txt"


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_config_path()

    def load(self) -> AppConfig:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return AppConfig()

        defaults = asdict(AppConfig())
        merged = {**defaults, **{key: value for key, value in data.items() if key in defaults}}
        return AppConfig(**merged)

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
