"""Brand profile persistent storage — separate JSON files for prod / test envs.

- prod env: 讀寫 BRANDS_PATH (default data/brands.json)
- test env: 讀 prod + test 合併（同 id 時 test 覆蓋），寫只入 BRANDS_TEST_PATH
  (default data/brands_test.json)

Each file has its own asyncio lock + atomic write.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Literal

Env = Literal["prod", "test"]

BRANDS_PATH = Path(os.getenv("BRANDS_PATH", "data/brands.json"))
BRANDS_TEST_PATH = Path(os.getenv("BRANDS_TEST_PATH", "data/brands_test.json"))

_LOCKS: dict[Env, asyncio.Lock] = {
    "prod": asyncio.Lock(),
    "test": asyncio.Lock(),
}


def _path_for(env: Env) -> Path:
    return BRANDS_PATH if env == "prod" else BRANDS_TEST_PATH


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


async def _read_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


async def _write_file(path: Path, profiles: list[dict]) -> None:
    _ensure_parent_dir(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(profiles, ensure_ascii=False, indent=2)
    await asyncio.to_thread(tmp_path.write_text, payload, encoding="utf-8")
    await asyncio.to_thread(os.replace, tmp_path, path)


async def list_brands(env: Env = "prod") -> list[dict]:
    """Return brand list for an env.

    prod env: only prod file (no `source` field set).
    test env: prod ∪ test merged, test overrides prod on same id. Each entry
    gets a `source` field — "prod" / "test" / "test" (override; same value to
    keep frontend simple — just shows which file's data is being used).
    """
    if env == "prod":
        async with _LOCKS["prod"]:
            return await _read_file(BRANDS_PATH)

    # test env — merge
    async with _LOCKS["prod"], _LOCKS["test"]:
        prod_list = await _read_file(BRANDS_PATH)
        test_list = await _read_file(BRANDS_TEST_PATH)

    test_ids = {p.get("id") for p in test_list}
    merged: list[dict] = []
    for p in prod_list:
        if p.get("id") not in test_ids:
            merged.append({**p, "source": "prod"})
    for p in test_list:
        merged.append({**p, "source": "test"})
    return merged


async def upsert_brand(profile: dict, env: Env = "prod") -> dict:
    """Write profile to the env's file. Test env never touches prod file."""
    if not profile.get("id"):
        raise ValueError("profile.id is required")
    # Don't persist transient `source` field
    profile = {k: v for k, v in profile.items() if k != "source"}
    path = _path_for(env)
    async with _LOCKS[env]:
        profiles = await _read_file(path)
        idx = next((i for i, p in enumerate(profiles) if p.get("id") == profile["id"]), -1)
        if idx >= 0:
            profiles[idx] = profile
        else:
            profiles.append(profile)
        await _write_file(path, profiles)
        return profile


async def delete_brand(brand_id: str, env: Env = "prod") -> bool:
    """Delete from the env's file only.

    In test env, prod-only brands are not deletable (return False) — switch to
    prod env to delete a prod brand.
    """
    path = _path_for(env)
    async with _LOCKS[env]:
        profiles = await _read_file(path)
        new_profiles = [p for p in profiles if p.get("id") != brand_id]
        if len(new_profiles) == len(profiles):
            return False
        await _write_file(path, new_profiles)
        return True
