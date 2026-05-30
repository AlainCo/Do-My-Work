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
        temperature: float = 0.0,
    ) -> dict[str, object]: ...

    def chat(
        self,
        model: str,
        messages: list[MockChatMessage],
        stream: bool = False,
        temperature: float = 0.0,
    ) -> dict[str, object]: ...


class OllamaMockChatBehavior(Protocol):
    def matches(self, messages: list[MockChatMessage]) -> bool: ...

    def render(self, messages: list[MockChatMessage], temperature: float = 0.0) -> str: ...


@dataclass(frozen=True, slots=True)
class TranslatorChatBehavior:
    system_keyword_fr: str = "traducteur"
    system_keyword_en: str = "translator"
    
    pre_context_marker_start: str = "===BEGIN PREVIOUS CONTEXT===\n"
    pre_context_marker_end: str = "===END PREVIOUS CONTEXT===\n"
    marker_start: str = "===BEGIN SOURCE TEXT===\n"
    marker_end: str = "===END SOURCE TEXT===\n"
    post_context_marker_start: str = "===BEGIN FOLLOWING CONTEXT===\n"
    post_context_marker_end: str = "===END FOLLOWING CONTEXT===\n"
    translation_hints_marker_start: str = "===BEGIN TRANSLATION HINTS===\n"
    translation_hints_marker_end: str = "===END TRANSLATION HINTS===\n"
    
    emotive_prefix: str = "Je suis emotif. "

    def matches(self, messages: list[MockChatMessage]) -> bool:
        for message in messages:
            if message.role == "system" and (
                    self.system_keyword_en in message.content.lower()
                    or self.system_keyword_fr in message.content.lower()
                ):
                return True
        return False

    def render(self, messages: list[MockChatMessage], temperature: float = 0.0) -> str:
        content = self._render_translated_content(messages)
        if temperature > 0.2:
            return f"{self.emotive_prefix}{content}"
        return content

    def _render_translated_content(self, messages: list[MockChatMessage]) -> str:
        pre_context = self._extract_marked_section(
            messages,
            self.pre_context_marker_start,
            self.pre_context_marker_end,
        )
        source_text = self._extract_marked_section(
            messages,
            self.marker_start,
            self.marker_end,
        )
        post_context = self._extract_marked_section(
            messages,
            self.post_context_marker_start,
            self.post_context_marker_end,
        )
        
        translation_hints = self._extract_marked_section(
            messages,
            self.translation_hints_marker_start,
            self.translation_hints_marker_end,
        )

        translated = source_text.upper()
        if pre_context is None and post_context is None and translation_hints is None:
            return translated

        return (
            f"{self._wrap_optional(pre_context, '(', ') ')}"
            f"{self._wrap_optional(translation_hints, '<', '> ')}"
            f"{translated}"
            f"{self._wrap_optional(post_context, ' (', ')')}"
        )

    def _wrap_optional(self, value: str | None, prefix: str, suffix: str) -> str:
        return "" if value is None else f"{prefix}{value}{suffix}"

    def _extract_marked_section(
        self,
        messages: list[MockChatMessage],
        marker_start: str,
        marker_end: str,
    ) -> str | None:
        for message in reversed(messages):
            start_index = message.content.find(marker_start)
            if start_index == -1:
                continue

            source_start = start_index + len(marker_start)
            end_index = message.content.find(marker_end, source_start)
            if end_index == -1:
                continue

            return message.content[source_start:end_index]

        return None


@dataclass(frozen=True, slots=True)
class KeywordChatBehavior:
    keyword_responses: dict[str, str]
    fallback_prefix: str

    def matches(self, messages: list[MockChatMessage]) -> bool:
        del messages
        return True

    def render(self, messages: list[MockChatMessage], temperature: float = 0.0) -> str:
        del temperature
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
        temperature: float = 0.0,
    ) -> dict[str, object]:
        self._sleep_if_needed()
        del stream
        del temperature

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
        temperature: float = 0.0,
    ) -> dict[str, object]:
        self._sleep_if_needed()
        del stream

        content = self._render_chat_response(messages, temperature)

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

    def _render_chat_response(
        self,
        messages: list[MockChatMessage],
        temperature: float,
    ) -> str:
        for behavior in self.chat_behaviors:
            if behavior.matches(messages):
                return behavior.render(messages, temperature)

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