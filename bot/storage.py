from __future__ import annotations

import json
from typing import Any


class JsonStorage:
    def __init__(self, path: str) -> None:
        self.path = path

    def read(self) -> dict:
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def write(self, data: dict) -> None:
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)