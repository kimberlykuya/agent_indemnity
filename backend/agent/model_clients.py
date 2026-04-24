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

import json
import logging
import time
from typing import Any

from openai import OpenAI, APIError, APITimeoutError

from google import genai
from google.genai import types

from agent import config
from agent.prompts import ACTION_CONTROLLER_SYSTEM_PROMPT, FALLBACK_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_FEATHERLESS_BASE = "https://api.featherless.ai/v1"
_TIMEOUT_SECONDS  = 30

_ACTION_TOOL = types.Tool(
    functionDeclarations=[
        types.FunctionDeclaration(
            name="settle_premium",
            description="Settle the per-request USDC premium for an agent action.",
            parametersJsonSchema={
                "type": "object",
                "properties": {
                    "amount_usdc": {
                        "type": "number",
                        "description": "USDC amount to settle for this request.",
                    },
                    "route_category": {
                        "type": "string",
                        "description": "Assigned route category for the request.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Short justification for settling the premium.",
                    },
                },
                "required": ["amount_usdc", "route_category"],
            },
        ),
        types.FunctionDeclaration(
            name="slash_performance_bond",
            description="Slash the agent performance bond and pay the affected party.",
            parametersJsonSchema={
                "type": "object",
                "properties": {
                    "victim_address": {
                        "type": "string",
                        "description": "Recipient wallet for the slash payout.",
                    },
                    "payout_amount_usdc": {
                        "type": "number",
                        "description": "USDC payout to release from the bond.",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Short justification for the slash.",
                    },
                },
                "required": ["victim_address", "payout_amount_usdc", "reason"],
            },
        ),
    ]
)


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
                "X-Title":      "Agent Indemnity",
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


def _coerce_function_args(args: Any) -> dict[str, Any]:
    if isinstance(args, dict):
        return args
    if args is None:
        return {}
    if hasattr(args, "items"):
        return dict(args.items())
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_function_calls(response: Any) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []

    direct_calls = getattr(response, "function_calls", None)
    if direct_calls:
        for call in direct_calls:
            extracted.append(
                {
                    "name": getattr(call, "name", "") or "",
                    "args": _coerce_function_args(getattr(call, "args", None)),
                }
            )

    if extracted:
        return extracted

    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            if not function_call:
                continue
            extracted.append(
                {
                    "name": getattr(function_call, "name", "") or "",
                    "args": _coerce_function_args(getattr(function_call, "args", None)),
                }
            )
    return extracted


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


def call_gemini_action_controller(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Call Gemini Flash as an orchestration layer and return function calls."""
    client = _get_gemini()
    t0 = time.monotonic()
    try:
        logger.info("Calling Gemini action controller model=%s", config.GEMINI_ACTION_MODEL)
        response = client.models.generate_content(
            model=config.GEMINI_ACTION_MODEL,
            contents=json.dumps(context, ensure_ascii=True, indent=2),
            config=types.GenerateContentConfig(
                systemInstruction=ACTION_CONTROLLER_SYSTEM_PROMPT,
                temperature=0,
                tools=[_ACTION_TOOL],
                toolConfig=types.ToolConfig(
                    functionCallingConfig=types.FunctionCallingConfig(
                        mode=types.FunctionCallingConfigMode.ANY,
                        allowedFunctionNames=[
                            "settle_premium",
                            "slash_performance_bond",
                        ],
                    )
                ),
            ),
        )
        latency = int((time.monotonic() - t0) * 1000)
        calls = _extract_function_calls(response)
        for fc in calls:
            print(f"GEMINI_TOOL_CALL: {fc.get('name')} with args {fc.get('args')}")
            logger.info(
                "GEMINI_TOOL_CALL: %s with args %s",
                fc.get("name"),
                fc.get("args"),
            )
        logger.info(
            "Gemini action controller complete: model=%s latency_ms=%d function_calls=%d",
            config.GEMINI_ACTION_MODEL,
            latency,
            len(calls),
        )
        return calls
    except Exception as exc:
        raise ModelClientError(f"Gemini action controller error: {exc}") from exc
