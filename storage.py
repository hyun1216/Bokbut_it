"""Local JSON persistence for Bokbut_it (복붙잇)."""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any


def get_app_dir() -> Path:
    """Return the application base directory for both script and PyInstaller builds."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_data_file_path() -> Path:
    """Return the persistent JSON path (AppData\\Local\\Bokbut_it for .exe, ./data for dev)."""
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else (Path.home() / "AppData" / "Local")
        return base / "Bokbut_it" / "widget_data.json"
    return get_app_dir() / "data" / "widget_data.json"


def create_default_data() -> dict[str, Any]:
    """Return the initial default widget state."""
    return {
        "topmost": True,
        "alpha": 0.93,
        "window_pos": {"x": 100, "y": 100},
        "window_size": {"width": 360, "height": 540},
        "copy_cards": [],
        "memo": "",
        "shortcuts": [
            {
                "id": str(uuid.uuid4()),
                "name": "업무 기록 예시",
                "template": "[{오늘날짜} ({요일}) {현재시간}]\n업무 내용: {입력:업무내용}",
            }
        ],
    }


def _merge_with_defaults(loaded: Any) -> dict[str, Any]:
    """Ensure all required keys exist with valid types."""
    defaults = create_default_data()
    if not isinstance(loaded, dict):
        return defaults

    raw_alpha = loaded.get("alpha", defaults["alpha"])
    alpha_val = round(float(raw_alpha), 2) if isinstance(raw_alpha, (int, float)) else 0.93
    if alpha_val not in (1.0, 0.93, 0.78):
        alpha_val = 0.93

    result: dict[str, Any] = {
        "topmost": bool(loaded.get("topmost", defaults["topmost"])),
        "alpha": alpha_val,
        "window_pos": defaults["window_pos"],
        "window_size": defaults["window_size"],
        "copy_cards": [],
        "memo": loaded.get("memo", "") if isinstance(loaded.get("memo"), str) else "",
        "shortcuts": [],
    }

    pos = loaded.get("window_pos")
    if isinstance(pos, dict) and isinstance(pos.get("x"), int) and isinstance(pos.get("y"), int):
        result["window_pos"] = {"x": pos["x"], "y": pos["y"]}

    size = loaded.get("window_size")
    if (
        isinstance(size, dict)
        and isinstance(size.get("width"), int)
        and isinstance(size.get("height"), int)
    ):
        result["window_size"] = {
            "width": max(300, size["width"]),
            "height": max(380, size["height"]),
        }

    raw_cards = loaded.get("copy_cards")
    if isinstance(raw_cards, list):
        for item in raw_cards:
            if isinstance(item, dict):
                result["copy_cards"].append(
                    {
                        "id": str(item.get("id") or uuid.uuid4()),
                        "title": str(item.get("title", "")),
                        "content": str(item.get("content", "")),
                        "kind": "link" if item.get("kind") == "link" else "text",
                        "collapsed": bool(item.get("collapsed", False)),
                    }
                )

    raw_shortcuts = loaded.get("shortcuts")
    if isinstance(raw_shortcuts, list):
        for item in raw_shortcuts:
            if isinstance(item, dict):
                result["shortcuts"].append(
                    {
                        "id": str(item.get("id") or uuid.uuid4()),
                        "name": str(item.get("name", "")),
                        "template": str(item.get("template", "")),
                    }
                )
    else:
        result["shortcuts"] = defaults["shortcuts"]

    return result


def load_data() -> dict[str, Any]:
    """Load widget data from JSON, creating default file if absent or invalid."""
    data_path = get_data_file_path()
    data_path.parent.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        default_data = create_default_data()
        save_data(default_data)
        return default_data

    try:
        with data_path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        return _merge_with_defaults(loaded)
    except (OSError, json.JSONDecodeError):
        default_data = create_default_data()
        save_data(default_data)
        return default_data


def save_data(data: dict[str, Any]) -> bool:
    """Persist widget data to JSON atomically."""
    data_path = get_data_file_path()
    data_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = data_path.with_suffix(".json.tmp")

    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, data_path)
        return True
    except OSError:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return False
