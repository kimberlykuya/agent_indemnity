"""
agent/model_clients.py
-----------------------
Thin adapters for external inference providers.

Rules:
- No routing logic here.
- No business logic here.
- One place to swap model IDs or SDKs.
- All errors propagate up as ModelClientError.
"""

import logging
import time

from openai import OpenAI, APIError, APITimeoutError

from google import genai
from google.genai import types

from agent import config
from agent.prompts import FALLBACK_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_FEATHERLESS_BASE = "https://api.featherless.ai/v1"
_TIMEOUT_SECONDS  = 30


class ModelClientError(Exception):
    """Raised when a provider call fails unrecoverably."""


# ---------------------------------------------------------------------------
# Featherless (OpenAI-compatible)
# ---------------------------------------------------------------------------
_featherless_client: OpenAI | None = None


def _get_featherless() -> OpenAI:
    global _featherless_client
    if _featherless_client is None:
        _featherless_client = OpenAI(
            api_key=config.FEATHERLESS_API_KEY,
            base_url=_FEATHERLESS_BASE,
            timeout=_TIMEOUT_SECONDS,
        )
    return _featherless_client


def call_featherless(model: str, system_prompt: str, user_message: str) -> str:
    """Call a Featherless specialist model and return the reply text."""
    client = _get_featherless()
    t0 = time.monotonic()
    try:
        logger.info("Calling Featherless model=%s base_url=%s", model, _FEATHERLESS_BASE)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            extra_headers={
                "HTTP-Referer": "https://agentindemnity.io",
                "X-Title":      "AgentIndemnity",
            },
        )
        latency = int((time.monotonic() - t0) * 1000)
        logger.info("Featherless call complete: model=%s latency_ms=%d", model, latency)
        return response.choices[0].message.content or ""
    except APITimeoutError as exc:
        raise ModelClientError(f"Featherless timeout after {_TIMEOUT_SECONDS}s") from exc
    except APIError as exc:
        raise ModelClientError(f"Featherless API error {exc.status_code}: {exc.message}") from exc


# ---------------------------------------------------------------------------
# Gemini (google-genai SDK)
# ---------------------------------------------------------------------------
_gemini_client: genai.Client | None = None


def _get_gemini() -> genai.Client:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _gemini_client


def call_gemini_router(user_message: str, system_prompt: str) -> str:
    """Call Gemini Flash for routing classification. Returns raw response text."""
    client = _get_gemini()
    t0 = time.monotonic()
    try:
        logger.info("Calling Gemini router model=%s", config.GEMINI_ROUTER_MODEL)
        response = client.models.generate_content(
            model=config.GEMINI_ROUTER_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
            ),
        )
        latency = int((time.monotonic() - t0) * 1000)
        logger.info("Gemini router call complete: model=%s latency_ms=%d",
                    config.GEMINI_ROUTER_MODEL, latency)
        return response.text or ""
    except Exception as exc:
        raise ModelClientError(f"Gemini router error: {exc}") from exc


def call_gemini_fallback(user_message: str) -> str:
    """Call Gemini Pro for complex/fallback answer generation."""
    client = _get_gemini()
    t0 = time.monotonic()
    try:
        logger.info("Calling Gemini fallback model=%s", config.GEMINI_FALLBACK_MODEL)
        response = client.models.generate_content(
            model=config.GEMINI_FALLBACK_MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=FALLBACK_SYSTEM_PROMPT,
            ),
        )
        latency = int((time.monotonic() - t0) * 1000)
        logger.info("Gemini fallback call complete: model=%s latency_ms=%d",
                    config.GEMINI_FALLBACK_MODEL, latency)
        return response.text or ""
    except Exception as exc:
        raise ModelClientError(f"Gemini fallback error: {exc}") from exc
