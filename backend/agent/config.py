"""
agent/config.py
----------------
Single source of truth for route names, prices, model IDs, and env vars.

Import this module everywhere you need a route name, price, or model ID.
Never hardcode these strings in other files.

Startup validation
------------------
Call validate_config() once at application startup (e.g. in main.py).
The module itself is importable without side effects — no errors are raised
at import time, so tests can import it freely.
"""

import os

from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# ---------------------------------------------------------------------------
# Route name constants
# ---------------------------------------------------------------------------
GENERAL          = "general"
TECHNICAL        = "technical"
LEGAL_RISK       = "legal_risk"
FALLBACK_COMPLEX = "fallback_complex"

ALL_ROUTES = [GENERAL, TECHNICAL, LEGAL_RISK, FALLBACK_COMPLEX]

# ---------------------------------------------------------------------------
# Per-request USDC price map  (all values ≤ $0.01)
# ---------------------------------------------------------------------------
PRICE_MAP: dict[str, float] = {
    GENERAL:          0.001,
    TECHNICAL:        0.003,
    LEGAL_RISK:       0.005,
    FALLBACK_COMPLEX: 0.010,
}

# ---------------------------------------------------------------------------
# Routing confidence threshold
# Rules-based route is accepted when confidence >= this value.
# Below the threshold, Gemini classifier is consulted.
# ---------------------------------------------------------------------------
RULE_CONFIDENCE_THRESHOLD = 0.85

# ---------------------------------------------------------------------------
# Env var reads  (no KeyError at import time — validation is separate)
# ---------------------------------------------------------------------------
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY", "")
FEATHERLESS_API_KEY  = os.getenv("FEATHERLESS_API_KEY", "")

FEATHERLESS_GENERAL_MODEL = os.getenv("FEATHERLESS_GENERAL_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
FEATHERLESS_TECH_MODEL    = os.getenv("FEATHERLESS_TECH_MODEL",    "mistralai/Mistral-7B-Instruct-v0.3")
FEATHERLESS_LEGAL_MODEL   = os.getenv("FEATHERLESS_LEGAL_MODEL",   "mistralai/Mistral-7B-Instruct-v0.3")
GEMINI_ROUTER_MODEL   = os.getenv("GEMINI_ROUTER_MODEL",   "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-pro-preview")
GEMINI_ACTION_MODEL   = os.getenv("GEMINI_ACTION_MODEL",   GEMINI_ROUTER_MODEL)

# Route → model ID lookup
MODEL_MAP: dict[str, str] = {
    GENERAL:          FEATHERLESS_GENERAL_MODEL,
    TECHNICAL:        FEATHERLESS_TECH_MODEL,
    LEGAL_RISK:       FEATHERLESS_LEGAL_MODEL,
    FALLBACK_COMPLEX: GEMINI_FALLBACK_MODEL,
}

_REQUIRED = {
    "GEMINI_API_KEY":      GEMINI_API_KEY,
    "FEATHERLESS_API_KEY": FEATHERLESS_API_KEY,
}


def validate_config() -> None:
    """Raise RuntimeError if any required env var is missing.

    Call this once at application startup, not at import time.
    """
    missing = [k for k, v in _REQUIRED.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the values."
        )


def get_model_config() -> dict[str, str]:
    """Return the currently loaded provider/model configuration."""
    return {
        "featherless_general_model": FEATHERLESS_GENERAL_MODEL,
        "featherless_tech_model": FEATHERLESS_TECH_MODEL,
        "featherless_legal_model": FEATHERLESS_LEGAL_MODEL,
        "gemini_router_model": GEMINI_ROUTER_MODEL,
        "gemini_fallback_model": GEMINI_FALLBACK_MODEL,
        "gemini_action_model": GEMINI_ACTION_MODEL,
    }
