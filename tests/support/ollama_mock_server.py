from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from tests.support.ollama_mock_behavior import (
    MockChatMessage,
    OllamaMockBehavior,
    RuleBasedOllamaMockBehavior,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

import logging
import pprint
import json
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("mock.server")

class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: "RequestOptions | None" = None


class MessagePayload(BaseModel):
    role: str
    content: str


class RequestOptions(BaseModel):
    temperature: float = 0.0


class ChatRequest(BaseModel):
    model: str
    messages: list[MessagePayload]
    stream: bool = False
    options: RequestOptions | None = None

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        body = await request.body()
        logger.info(
            "REST request: %s %s\nBody: %s",
            request.method,
            request.url,
            body.decode(errors="ignore"))
        response = await call_next(request)
        return response


def create_app(behavior: OllamaMockBehavior | None = None) -> "FastAPI":
    try:
        from fastapi import FastAPI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "FastAPI is required for the Ollama mock server. "
            "Install it with: python -m pip install -e \".[mock-ollama]\""
        ) from exc

    active_behavior = behavior or RuleBasedOllamaMockBehavior()
    app = FastAPI()
    
    logger = logging.getLogger("mock.server")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:  # éviter doublons en mode reload
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

 
    
    app.add_middleware(RequestLoggerMiddleware)

    @app.get("/api/version")
    def version() -> dict[str, str]:
        return active_behavior.version()

    @app.get("/api/tags")
    def tags() -> dict[str, list[dict[str, object]]]:
        return active_behavior.tags()

    @app.post("/api/generate")
    def generate(request: GenerateRequest) -> dict[str, object]:
        return active_behavior.generate(
            model=request.model,
            prompt=request.prompt,
            stream=request.stream,
            temperature=request.options.temperature if request.options else 0.0,
        )

    @app.post("/api/chat")
    def chat(request: ChatRequest) -> dict[str, object]:
        messages = [
            MockChatMessage(role=message.role, content=message.content)
            for message in request.messages
        ]
        return active_behavior.chat(
            model=request.model,
            messages=messages,
            stream=request.stream,
            temperature=request.options.temperature if request.options else 0.0,
        )

    return app


def main() -> None:
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Uvicorn is required to run the Ollama mock server. "
            "Install it with: python -m pip install -e \".[mock-ollama]\""
        ) from exc

    module_path = "tests.support.ollama_mock_server:create_app"
    uvicorn.run(
        module_path, 
        factory=True,
        host="127.0.0.1", 
        port=11434,
        log_level="debug")


if __name__ == "__main__":
    main()