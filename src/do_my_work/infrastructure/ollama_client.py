from __future__ import annotations

from dataclasses import dataclass
from string import Template
from typing import Mapping

import httpx

from do_my_work.domain.models import TranslatorProfileConfig, WorkspaceConfig


class TranslatorProfileNotFoundError(KeyError):
    pass


class PromptTemplateParameterError(ValueError):
    pass


class OllamaResponseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OllamaChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class RenderedTranslatorRequest:
    profile_name: str
    profile: TranslatorProfileConfig
    messages: list[OllamaChatMessage]


class OllamaChatClient:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        # TODO mettre le timeout dans la config
        self._http_client = http_client or httpx.Client(timeout=180.0)
        self._owns_http_client = http_client is None

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def render_translator_request(
        self,
        config: WorkspaceConfig,
        profile_name: str,
        parameters: Mapping[str, object],
    ) -> RenderedTranslatorRequest:
        profile = config.llm.translator.get(profile_name)
        if profile is None:
            raise TranslatorProfileNotFoundError(profile_name)

        substitution_map = {key: str(value) for key, value in parameters.items()}
        try:
            system_prompt = Template(profile.system_prompt).substitute(substitution_map)
            user_prompt = Template(profile.user_prompt).substitute(substitution_map)
        except KeyError as exc:
            raise PromptTemplateParameterError(str(exc)) from exc

        return RenderedTranslatorRequest(
            profile_name=profile_name,
            profile=profile,
            messages=[
                OllamaChatMessage(role="system", content=system_prompt),
                OllamaChatMessage(role="user", content=user_prompt),
            ],
        )

    def translate_fragment(
        self,
        config: WorkspaceConfig,
        profile_name: str,
        parameters: Mapping[str, object],
    ) -> str:
        rendered_request = self.render_translator_request(
            config=config,
            profile_name=profile_name,
            parameters=parameters,
        )
        response = self._http_client.post(
            _build_chat_url(rendered_request.profile.url),
            headers=_build_headers(rendered_request.profile),
            json={
                "model": rendered_request.profile.model,
                "messages": [
                    {"role": message.role, "content": message.content}
                    for message in rendered_request.messages
                ],
                "stream": False,
                "options": {"temperature": rendered_request.profile.temperature},
            },
        )
        response.raise_for_status()
        payload = response.json()

        try:
            return payload["message"]["content"]
        except KeyError as exc:
            raise OllamaResponseError("Missing Ollama chat response content.") from exc


def _build_headers(profile: TranslatorProfileConfig) -> dict[str, str]:
    if profile.credential is None:
        return {}
    return {"Authorization": f"Bearer {profile.credential}"}


def _build_chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/chat"