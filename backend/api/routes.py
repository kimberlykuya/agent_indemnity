"""
api/routes.py
--------------
Thin scaffold around the orchestrator.

Sprint 2: callable wrapper only.
Sprint 3: attach to FastAPI router with full WebSocket and REST.
"""

from api.schemas import ChatRequest, ChatResponse
from agent.customer_service import handle_request


def chat(request: ChatRequest) -> ChatResponse:
    """Call the orchestrator and validate the response shape."""
    raw = handle_request(message=request.message, user_id=request.user_id)
    return ChatResponse(**raw)
