"""Feature flag registry — single source of truth for experimental toggles.

Each flag has a prod default + test default. Request can override via
`feature_flags` dict. Once a flag proves out, flip its prod default to True
and (later) remove the flag once both branches converge.
"""

from app.models.schemas import Env

# Schema: flag_name → {"prod": bool, "test": bool, "description": str}
FEATURE_FLAGS: dict[str, dict] = {
    "use_experimental_cleaner_prompt": {
        "prod": False,
        "test": True,
        "description": "示範 flag — 切換 ai_cleaner 嘅 prompt variant，驗證 plumbing 通到。",
    },
}


def get_defaults(env: Env) -> dict[str, bool]:
    """Return all flag defaults for the given environment."""
    return {name: spec[env] for name, spec in FEATURE_FLAGS.items()}


def resolve_flags(env: Env, overrides: dict[str, bool] | None = None) -> dict[str, bool]:
    """Resolve effective flag values: env defaults overlaid with request overrides.

    Unknown flag keys in `overrides` are silently dropped — registry is source of truth.
    """
    resolved = get_defaults(env)
    if overrides:
        for name, value in overrides.items():
            if name in FEATURE_FLAGS:
                resolved[name] = bool(value)
    return resolved
