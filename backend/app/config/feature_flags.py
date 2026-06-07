"""Feature flag registry — single source of truth for experimental toggles.

Each flag has a prod default + test default. Request can override via
`feature_flags` dict. Once a flag proves out, flip its prod default to True
and (later) remove the flag once both branches converge.
"""

from app.models.schemas import Env

# Schema: flag_name → {"prod": bool, "test": bool, "description": str}
FEATURE_FLAGS: dict[str, dict] = {
    "add_shopline_spacing": {
        "prod": False,
        "test": True,
        "description": "喺 Shopline HTML top-level block 之間插 <p><br></p>，避免貼入 Shopline editor 之後段落逼埋。",
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
