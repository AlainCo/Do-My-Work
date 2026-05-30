import json

import httpx
import pytest

from do_my_work.domain.models import LlmConfig, TranslatorProfileConfig, WorkspaceConfig
from do_my_work.infrastructure.ollama_client import (
    OllamaChatClient,
    OllamaResponseError,
    PromptTemplateParameterError,
    TranslatorProfileNotFoundError,
)


def test_ollama_chat_client_renders_translator_prompts_and_calls_chat_endpoint() -> None:
    captured_request: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["authorization"] = request.headers.get("Authorization")
        captured_request["timeout"] = request.extensions["timeout"]
        captured_request["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "BONJOUR MONDE",
                }
            },
        )

    config = WorkspaceConfig(
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="mock-llama",
                    credential="secret-token",
                    timeout_seconds=42.5,
                    temperature=0.3,
                    system_prompt="You are a translator.",
                    user_prompt=(
                        "===BEGIN SOURCE TEXT===\n"
                        "${input_fragment}\n"
                        "===END SOURCE TEXT===\n"
                    ),
                )
            }
        )
    )
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = OllamaChatClient(http_client=http_client)

    result = client.translate_fragment(
        config=config,
        profile_name="technical",
        parameters={"input_fragment": "Bonjour monde"},
    )

    assert result == "BONJOUR MONDE"
    assert captured_request["url"] == "http://mock.example:11434/api/chat"
    assert captured_request["authorization"] == "Bearer secret-token"
    assert captured_request["timeout"] == {
        "connect": 42.5,
        "read": 42.5,
        "write": 42.5,
        "pool": 42.5,
    }
    assert captured_request["payload"] == {
        "model": "mock-llama",
        "messages": [
            {"role": "system", "content": "You are a translator."},
            {
                "role": "user",
                "content": (
                    "===BEGIN SOURCE TEXT===\n"
                    "Bonjour monde\n"
                    "===END SOURCE TEXT===\n"
                ),
            },
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }


def test_ollama_chat_client_retries_timeout_and_eventually_succeeds() -> None:
    captured_attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_attempts.append(len(captured_attempts) + 1)
        if len(captured_attempts) < 3:
            raise httpx.ReadTimeout("temporary timeout", request=request)
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "RECOVERED"}},
        )

    config = WorkspaceConfig(
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="mock-llama",
                    timeout_seconds=5.0,
                    max_retries=2,
                    system_prompt="You are a translator.",
                    user_prompt="${input_fragment}",
                )
            }
        )
    )
    client = OllamaChatClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = client.translate_fragment(
        config=config,
        profile_name="technical",
        parameters={"input_fragment": "Bonjour monde"},
    )

    assert result == "RECOVERED"
    assert captured_attempts == [1, 2, 3]


def test_ollama_chat_client_retries_server_error_and_eventually_succeeds() -> None:
    captured_attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_attempts.append(len(captured_attempts) + 1)
        if len(captured_attempts) < 2:
            return httpx.Response(503, request=request, json={"error": "temporary outage"})
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "RECOVERED"}},
        )

    config = WorkspaceConfig(
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="mock-llama",
                    max_retries=1,
                    system_prompt="You are a translator.",
                    user_prompt="${input_fragment}",
                )
            }
        )
    )
    client = OllamaChatClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    result = client.translate_fragment(
        config=config,
        profile_name="technical",
        parameters={"input_fragment": "Bonjour monde"},
    )

    assert result == "RECOVERED"
    assert captured_attempts == [1, 2]


def test_ollama_chat_client_does_not_retry_client_error() -> None:
    captured_attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_attempts.append(len(captured_attempts) + 1)
        return httpx.Response(400, request=request, json={"error": "bad request"})

    config = WorkspaceConfig(
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="mock-llama",
                    max_retries=3,
                    system_prompt="You are a translator.",
                    user_prompt="${input_fragment}",
                )
            }
        )
    )
    client = OllamaChatClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(httpx.HTTPStatusError, match="400 Bad Request"):
        client.translate_fragment(
            config=config,
            profile_name="technical",
            parameters={"input_fragment": "Bonjour monde"},
        )

    assert captured_attempts == [1]


def test_ollama_chat_client_raises_when_translator_profile_is_missing() -> None:
    client = OllamaChatClient(http_client=httpx.Client(transport=httpx.MockTransport(_unused)))

    with pytest.raises(TranslatorProfileNotFoundError, match="technical"):
        client.translate_fragment(
            config=WorkspaceConfig(),
            profile_name="technical",
            parameters={"input_fragment": "Bonjour monde"},
        )


def test_ollama_chat_client_raises_when_template_parameter_is_missing() -> None:
    config = WorkspaceConfig(
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="mock-llama",
                    system_prompt="You are a translator for ${language}.",
                    user_prompt="${input_fragment}",
                )
            }
        )
    )
    client = OllamaChatClient(http_client=httpx.Client(transport=httpx.MockTransport(_unused)))

    with pytest.raises(PromptTemplateParameterError, match="language"):
        client.translate_fragment(
            config=config,
            profile_name="technical",
            parameters={"input_fragment": "Bonjour monde"},
        )


def test_ollama_chat_client_raises_when_response_has_no_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"done": True})

    config = WorkspaceConfig(
        llm=LlmConfig(
            translator={
                "technical": TranslatorProfileConfig(
                    url="http://mock.example:11434",
                    model="mock-llama",
                    system_prompt="You are a translator.",
                    user_prompt="${input_fragment}",
                )
            }
        )
    )
    client = OllamaChatClient(http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(OllamaResponseError, match="Missing Ollama chat response content"):
        client.translate_fragment(
            config=config,
            profile_name="technical",
            parameters={"input_fragment": "Bonjour monde"},
        )


def _unused(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"Unexpected HTTP request: {request.url}")