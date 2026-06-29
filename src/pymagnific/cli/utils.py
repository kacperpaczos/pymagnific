"""CLI utilities."""

from __future__ import annotations

import asyncio
import json
from typing import Any


def print_json(data: Any) -> None:
    if isinstance(data, str) and "\n" in data:
        print(data)
        return
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def run_async(coro):
    return asyncio.run(coro)
