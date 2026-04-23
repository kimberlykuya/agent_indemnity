from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent import config
from agent.route_categories import RouteCategory


class InferenceProvider(str, Enum):
    FEATHERLESS = "featherless"
    GEMINI = "gemini"


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    provider: InferenceProvider
    api_base: str | None


_MODEL_MAP = {
    RouteCategory.GENERAL: ModelSpec(
        model_id=config.FEATHERLESS_GENERAL_MODEL,
        provider=InferenceProvider.FEATHERLESS,
        api_base="https://api.featherless.ai/v1",
    ),
    RouteCategory.TECHNICAL: ModelSpec(
        model_id=config.FEATHERLESS_TECH_MODEL,
        provider=InferenceProvider.FEATHERLESS,
        api_base="https://api.featherless.ai/v1",
    ),
    RouteCategory.LEGAL: ModelSpec(
        model_id=config.FEATHERLESS_LEGAL_MODEL,
        provider=InferenceProvider.FEATHERLESS,
        api_base="https://api.featherless.ai/v1",
    ),
    RouteCategory.FALLBACK: ModelSpec(
        model_id=config.GEMINI_FALLBACK_MODEL,
        provider=InferenceProvider.GEMINI,
        api_base=None,
    ),
}


def get_model(category: RouteCategory) -> ModelSpec:
    return _MODEL_MAP[category]
