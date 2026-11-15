"""Chat routes - Groq LLM chat completions."""

from fastapi import APIRouter, Depends, HTTPException, status
import httpx
import structlog
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from services.api.src.config import settings

router = APIRouter()
logger = structlog.get_logger()


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    max_tokens: Optional[int] = Field(default=2000, ge=1, le=4096)
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)
    stream: Optional[bool] = Field(default=False)


class ChatChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Dict[str, Any]
    usage_breakdown: Optional[Dict[str, Any]] = None
    system_fingerprint: Optional[str] = None
    x_groq: Optional[Dict[str, Any]] = None


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: ChatCompletionRequest,
) -> ChatCompletionResponse:
    """
    Generate chat completions using Groq LLM (OpenAI-compatible API).
    """
    logger.info(
        "chat_completion_started",
        model=request.model,
        message_count=len(request.messages),
    )

    if not settings.LLM_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "LLM_NOT_CONFIGURED",
                    "message": "LLM API key not configured",
                }
            },
        )

    base_url = settings.LLM_API_URL or "https://api.openai.com/v1"
    model = request.model or settings.LLM_MODEL
    max_tokens = min(
        request.max_tokens or settings.LLM_MAX_TOKENS,
        settings.LLM_MAX_TOKENS,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [msg.model_dump() for msg in request.messages],
                    "max_tokens": max_tokens,
                    "temperature": request.temperature,
                    "stream": request.stream,
                },
            )
        response.raise_for_status()
        data = response.json()

        return ChatCompletionResponse(**data)

    except httpx.HTTPStatusError as e:
        logger.error("llm_api_error", status=e.response.status_code, error=e.response.text)
        raise HTTPException(
            status_code=e.response.status_code,
            detail={
                "error": {
                    "code": "LLM_API_ERROR",
                    "message": f"LLM API error: {e.response.text}",
                }
            },
        )
    except Exception as e:
        logger.error("llm_request_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "LLM_REQUEST_FAILED",
                    "message": f"LLM request failed: {str(e)}",
                }
            },
        )


@router.get("/chat/models")
async def list_models() -> Dict[str, Any]:
    """
    List available models from the LLM provider.
    """
    if not settings.LLM_API_KEY:
        return {"models": [], "error": "LLM not configured"}

    base_url = settings.LLM_API_URL or "https://api.openai.com/v1"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{settings.LLM_API_URL.rstrip('/') if settings.LLM_API_URL else 'https://api.openai.com/v1'}/models",
                headers={
                    "Authorization": f"Bearer {settings.LLM_API_KEY}",
                },
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("models_list_failed", error=str(e))
        return {"models": [], "error": str(e)}