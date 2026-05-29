from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import sleep
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MockChatMessage:
    role: str
    content: str


class OllamaMockBehavior(Protocol):
    def version(self) -> dict[str, str]: ...

    def tags(self) -> dict[str, list[dict[str, object]]]: ...

    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
    ) -> dict[str, object]: ...

    def chat(
        self,
        model: str,
        messages: list[MockChatMessage],
        stream: bool = False,
    ) -> dict[str, object]: ...


class OllamaMockChatBehavior(Protocol):
    def matches(self, messages: list[MockChatMessage]) -> bool: ...

    def render(self, messages: list[MockChatMessage]) -> str: ...


@dataclass(frozen=True, slots=True)
class TranslatorChatBehavior:
    system_keyword: str = "translator"
    marker_start: str = "===BEGIN SOURCE TEXT===\n"
    marker_end: str = "===END SOURCE TEXT===\n"

    def matches(self, messages: list[MockChatMessage]) -> bool:
        for message in messages:
            if message.role == "system" and self.system_keyword in message.content.lower():
                return True
        return False

    def render(self, messages: list[MockChatMessage]) -> str:
        return self._extract_source_text(messages).upper()

    def _extract_source_text(self, messages: list[MockChatMessage]) -> str:
        for message in reversed(messages):
            start_index = message.content.find(self.marker_start)
            if start_index == -1:
                continue

            source_start = start_index + len(self.marker_start)
            end_index = message.content.find(self.marker_end, source_start)
            if end_index == -1:
                continue

            return message.content[source_start:end_index]

        return ""


@dataclass(frozen=True, slots=True)
class KeywordChatBehavior:
    keyword_responses: dict[str, str]
    fallback_prefix: str

    def matches(self, messages: list[MockChatMessage]) -> bool:
        del messages
        return True

    def render(self, messages: list[MockChatMessage]) -> str:
        prompt = _extract_last_user_message(messages)
        lowered_prompt = prompt.lower()
        for keyword, response in self.keyword_responses.items():
            if keyword in lowered_prompt:
                return response
        return f"{self.fallback_prefix}{prompt}"


@dataclass(slots=True)
class RuleBasedOllamaMockBehavior:
    advertised_model: str = "mock-llama"
    version_value: str = "0.0.0-mock"
    latency_seconds: float = 0.0
    keyword_responses: dict[str, str] = field(
        default_factory=lambda: {
            "bonjour": "Bonjour ! Ceci est une reponse mock.",
            "python": "Python est un excellent choix pour prototyper rapidement.",
        }
    )
    fallback_prefix: str = "[mock] reponse generee pour : "
    model_size: int = 123_456_789
    chat_behaviors: list[OllamaMockChatBehavior] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.chat_behaviors:
            return

        self.chat_behaviors.extend(
            [
                TranslatorChatBehavior(),
                KeywordChatBehavior(
                    keyword_responses=self.keyword_responses,
                    fallback_prefix=self.fallback_prefix,
                ),
            ]
        )

    def version(self) -> dict[str, str]:
        return {"version": self.version_value}

    def tags(self) -> dict[str, list[dict[str, object]]]:
        return {
            "models": [
                {
                    "name": self.advertised_model,
                    "modified_at": _utc_timestamp(),
                    "size": self.model_size,
                }
            ]
        }

    def generate(
        self,
        model: str,
        prompt: str,
        stream: bool = False,
    ) -> dict[str, object]:
        self._sleep_if_needed()
        del stream

        return {
            "model": model,
            "created_at": _utc_timestamp(),
            "response": self._render_response(prompt),
            "done": True,
        }

    def chat(
        self,
        model: str,
        messages: list[MockChatMessage],
        stream: bool = False,
    ) -> dict[str, object]:
        self._sleep_if_needed()
        del stream

        content = self._render_chat_response(messages)

        return {
            "model": model,
            "created_at": _utc_timestamp(),
            "message": {
                "role": "assistant",
                "content": content,
            },
            "done": True,
        }

    def _render_response(self, prompt: str) -> str:
        lowered_prompt = prompt.lower()
        for keyword, response in self.keyword_responses.items():
            if keyword in lowered_prompt:
                return response
        return f"{self.fallback_prefix}{prompt}"

    def _render_chat_response(self, messages: list[MockChatMessage]) -> str:
        for behavior in self.chat_behaviors:
            if behavior.matches(messages):
                return behavior.render(messages)

        return ""

    def _sleep_if_needed(self) -> None:
        if self.latency_seconds > 0:
            sleep(self.latency_seconds)


def _extract_last_user_message(messages: list[MockChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return ""


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()