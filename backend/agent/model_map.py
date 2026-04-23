"""
agent/model_map.py
-------------------
Maps each RouteCategory to a concrete inference model.

Provider hierarchy from plan.md:
  - Featherless (OpenAI-compatible API) — cost-efficient specialists
  - Gemini Flash  — router / orchestrator
  - Gemini Pro    — deep-reasoning fallback

Model IDs are read from environment variables so they can be updated
without a code change (Featherless model IDs change; verify before demo).
"""

import os
from dataclasses import dataclass
from enum import Enum

from .route_categories import RouteCategory


class InferenceProvider(str, Enum):
    GEMINI = "gemini"
    FEATHERLESS = "featherless"


@dataclass(frozen=True)
class ModelSpec:
    """Descriptor for a single inference model."""

    provider: InferenceProvider
    model_id: str          # Passed verbatim to the API
    api_base: str | None   # For Featherless: OpenAI-compat base URL; None → native SDK
    context: str           # One-line description for logs/dashboards

    @property
    def is_gemini(self) -> bool:
        return self.provider == InferenceProvider.GEMINI

    @property
    def is_featherless(self) -> bool:
        return self.provider == InferenceProvider.FEATHERLESS


# ---------------------------------------------------------------------------
# Well-known endpoints / model IDs
# ---------------------------------------------------------------------------
_FEATHERLESS_BASE = "https://api.featherless.ai/v1"

# Gemini model IDs — hardcoded; no extra env vars needed
_GEMINI_FLASH_ID = "gemini-2.5-flash-preview-04-17"
_GEMINI_PRO_ID   = "gemini-2.5-pro-preview-03-25"

# Featherless model IDs — read from .env.example vars
_FEATHERLESS_GENERAL_ID = os.getenv("FEATHERLESS_GENERAL_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
_FEATHERLESS_LEGAL_ID   = os.getenv("FEATHERLESS_LEGAL_MODEL",   "mistralai/Mistral-7B-Instruct-v0.3")
_FEATHERLESS_TECH_ID    = os.getenv("FEATHERLESS_TECH_MODEL",    "mistralai/Mistral-7B-Instruct-v0.3")

# ---------------------------------------------------------------------------
# Authoritative model map — keyed by RouteCategory
# ---------------------------------------------------------------------------
MODEL_MAP: dict[RouteCategory, ModelSpec] = {
    RouteCategory.GENERAL: ModelSpec(
        provider=InferenceProvider.FEATHERLESS,
        model_id=_FEATHERLESS_GENERAL_ID,
        api_base=_FEATHERLESS_BASE,
        context="General customer-service specialist (Featherless)",
    ),
    RouteCategory.LEGAL: ModelSpec(
        provider=InferenceProvider.FEATHERLESS,
        model_id=_FEATHERLESS_LEGAL_ID,
        api_base=_FEATHERLESS_BASE,
        context="Legal / risk / refund specialist (Featherless)",
    ),
    RouteCategory.TECHNICAL: ModelSpec(
        provider=InferenceProvider.FEATHERLESS,
        model_id=_FEATHERLESS_TECH_ID,
        api_base=_FEATHERLESS_BASE,
        context="Technical support specialist (Featherless)",
    ),
    RouteCategory.FALLBACK: ModelSpec(
        provider=InferenceProvider.GEMINI,
        model_id=_GEMINI_PRO_ID,
        api_base=None,
        context="Deep-reasoning fallback (Gemini Pro)",
    ),
}

# Separate entry for the router/orchestrator itself (not in MODEL_MAP because
# it is not a reply model — it is used before category assignment).
ROUTER_MODEL: ModelSpec = ModelSpec(
    provider=InferenceProvider.GEMINI,
    model_id=_GEMINI_FLASH_ID,
    api_base=None,
    context="Router / orchestrator (Gemini Flash)",
)


def get_model(category: RouteCategory) -> ModelSpec:
    """Return the ModelSpec for the given RouteCategory.

    Raises KeyError if the category has no mapping (guards against
    future enum extensions that forget to update this table).
    """
    if category not in MODEL_MAP:
        raise KeyError(
            f"No model mapped for RouteCategory '{category}'. "
            "Update MODEL_MAP in model_map.py."
        )
    return MODEL_MAP[category]
