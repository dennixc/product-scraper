"""Brand profile persistent storage — JSON file with asyncio lock and atomic writes."""

import asyncio
import json
import os
from pathlib import Path

_LOCK = asyncio.Lock()
BRANDS_PATH = Path(os.getenv("BRANDS_PATH", "data/brands.json"))


def _ensure_parent_dir() -> None:
    BRANDS_PATH.parent.mkdir(parents=True, exist_ok=True)


async def _read_all() -> list[dict]:
    if not BRANDS_PATH.exists():
        return []
    try:
        text = await asyncio.to_thread(BRANDS_PATH.read_text, encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


async def _write_all(profiles: list[dict]) -> None:
    _ensure_parent_dir()
    tmp_path = BRANDS_PATH.with_suffix(BRANDS_PATH.suffix + ".tmp")
    payload = json.dumps(profiles, ensure_ascii=False, indent=2)
    await asyncio.to_thread(tmp_path.write_text, payload, encoding="utf-8")
    await asyncio.to_thread(os.replace, tmp_path, BRANDS_PATH)


async def list_brands() -> list[dict]:
    async with _LOCK:
        return await _read_all()


async def upsert_brand(profile: dict) -> dict:
    if not profile.get("id"):
        raise ValueError("profile.id is required")
    async with _LOCK:
        profiles = await _read_all()
        idx = next((i for i, p in enumerate(profiles) if p.get("id") == profile["id"]), -1)
        if idx >= 0:
            profiles[idx] = profile
        else:
            profiles.append(profile)
        await _write_all(profiles)
        return profile


async def delete_brand(brand_id: str) -> bool:
    async with _LOCK:
        profiles = await _read_all()
        new_profiles = [p for p in profiles if p.get("id") != brand_id]
        if len(new_profiles) == len(profiles):
            return False
        await _write_all(new_profiles)
        return True
