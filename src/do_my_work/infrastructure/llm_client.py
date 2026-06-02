from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from statistics import pvariance
from string import Template
import threading
from time import perf_counter, time
from typing import Mapping

import httpx

from do_my_work.domain.models import TranslatorProfileConfig, WorkspaceConfig

def progress_dots(stop_event, interval=1):
    start = time()
    while not stop_event.wait(interval):
        elapsed = int(time() - start)
        text = f"Waiting... {elapsed}s"
        print(f"\r{text:<30}", end="", flush=True)
    print("\r" + " " * 30 + "\r", end="", flush=True)

class TranslatorProfileNotFoundError(KeyError):
    pass


class PromptTemplateParameterError(ValueError):
    pass


class OllamaLlmResponseError(ValueError):
    pass


class OpenAiLlmResponseError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LlmChatMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class RenderedTranslatorRequest:
    profile_name: str
    profile: TranslatorProfileConfig
    messages: list[LlmChatMessage]


@dataclass(frozen=True, slots=True)
class LlmCallTimingSummary:
    attempt_count: int = 0
    average_elapsed_seconds: float = 0.0
    variance_elapsed_seconds: float = 0.0


class UnsupportedLlmProviderError(ValueError):
    pass


class AbstractLlmClient(ABC):
    
    trace: bool = True
    
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client or httpx.Client()
        self._owns_http_client = http_client is None
        self._logger = logging.getLogger(__name__)
        self._elapsed_attempt_seconds: list[float] = []
        
        # checking if client is already tagged first
        already_tagged = getattr(http_client, "_llm_logger_attached", False)
        
        if http_client is None:
            # case 1 instance creation attach instance methods
            self._http_client = httpx.Client(event_hooks={
                "request": [self._log_request_instance],
                "response": [self._log_response_instance]
            })
            self._owns_http_client = True
        else:
            # case 2, already created
            self._http_client = http_client
            self._owns_http_client = False
            
            # add static hook only if not already tagged
            if not already_tagged:
                self._http_client.event_hooks.setdefault("request", []).append(self._log_request_shared)
                self._http_client.event_hooks.setdefault("response", []).append(self._log_response_shared)

        # tagging the client whatever happened
        setattr(self._http_client, "_llm_logger_attached", True)

    # --- 1. hook for single instance (instance methods) ---
    def _log_request_instance(self, request: httpx.Request) -> None:
        self._execute_request_logging(self._logger, request)

    def _log_response_instance(self, response: httpx.Response) -> None:
        self._execute_response_logging(self._logger, response)

    # --- 2. Hooks for shared instances (static methods) ---
    @staticmethod
    def _log_request_shared(request: httpx.Request) -> None:
        logger = logging.getLogger(__name__)
        AbstractLlmClient._execute_request_logging(logger, request)

    @staticmethod
    def _log_response_shared(response: httpx.Response) -> None:
        logger = logging.getLogger(__name__)
        AbstractLlmClient._execute_response_logging(logger, response)

    # --- 3. shared logic---
    @staticmethod
    def _execute_request_logging(logger: logging.Logger, request: httpx.Request) -> None:
        if AbstractLlmClient.trace:
            try:
                body = request.read().decode("utf-8", errors="replace")
                logger.info(f"\n=== >>> Request sent ({request.method} {request.url}) ===\n{body}\n")
            except Exception as e:
                logger.error(f"Unable to log request : {e}")

    @staticmethod
    def _execute_response_logging(logger: logging.Logger, response: httpx.Response) -> None:
        if AbstractLlmClient.trace:
            try:
                response.read()
                logger.info(f"\n=== <<< Response received ({response.status_code}) ===\n{response.text}\n")
            except Exception as e:
                logger.error(f"Unable to log response : {e}")
    # --- end loggers tricks

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def get_timing_summary(self) -> LlmCallTimingSummary:
        if not self._elapsed_attempt_seconds:
            return LlmCallTimingSummary()

        average_elapsed_seconds = sum(self._elapsed_attempt_seconds) / len(
            self._elapsed_attempt_seconds
        )
        variance_elapsed_seconds = pvariance(self._elapsed_attempt_seconds)
        return LlmCallTimingSummary(
            attempt_count=len(self._elapsed_attempt_seconds),
            average_elapsed_seconds=average_elapsed_seconds,
            variance_elapsed_seconds=variance_elapsed_seconds,
        )

    def _record_attempt_duration(self, elapsed_seconds: float) -> None:
        self._elapsed_attempt_seconds.append(elapsed_seconds)

    def get_attempt_durations(self) -> list[float]:
        return list(self._elapsed_attempt_seconds)

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
                LlmChatMessage(role="system", content=system_prompt),
                LlmChatMessage(role="user", content=user_prompt),
            ],
        )

    @abstractmethod
    def translate_fragment(
        self,
        config: WorkspaceConfig,
        profile_name: str,
        parameters: Mapping[str, object],
    ) -> str:
        raise NotImplementedError()


class OllamaLlmClient(AbstractLlmClient):
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
        response = self._post_with_retries(rendered_request)
        payload = response.json()

        try:
            return payload["message"]["content"]
        except KeyError as exc:
            raise OllamaLlmResponseError("Missing Ollama chat response content.") from exc

    def _post_with_retries(self, rendered_request: RenderedTranslatorRequest) -> httpx.Response:
        max_attempt_count = rendered_request.profile.max_retries + 1
        for attempt_index in range(max_attempt_count):
            started_at = perf_counter()
            stop_event = threading.Event()
            t = threading.Thread(target=progress_dots, args=(stop_event,), daemon=True)
            try:
                t.start()
                print(f"OllamaLlmClient call in progress: profile={rendered_request.profile_name} attempt={attempt_index + 1} : ",end="\n", flush=True)
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
                    timeout=rendered_request.profile.timeout_seconds,
                )
                response.raise_for_status()
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                self._logger.info(
                    "LLM call completed: profile=%s attempt=%s elapsed_seconds=%.3f http_status_code=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    response.status_code,
                )
                return response
            except httpx.TimeoutException:
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                will_retry = attempt_index < rendered_request.profile.max_retries
                self._logger.warning(
                    "LLM call failed: profile=%s attempt=%s elapsed_seconds=%.3f error_category=timeout will_retry=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    will_retry,
                )
                if not will_retry:
                    raise
            except httpx.HTTPStatusError as exc:
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                will_retry = (
                    attempt_index < rendered_request.profile.max_retries
                    and exc.response.status_code >= 500
                )
                self._logger.warning(
                    "LLM call failed: profile=%s attempt=%s elapsed_seconds=%.3f error_category=http_status http_status_code=%s will_retry=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    exc.response.status_code,
                    will_retry,
                )
                if not will_retry or exc.response.status_code < 500:
                    raise
            except httpx.RequestError:
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                will_retry = attempt_index < rendered_request.profile.max_retries
                self._logger.warning(
                    "LLM call failed: profile=%s attempt=%s elapsed_seconds=%.3f error_category=request_error will_retry=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    will_retry,
                )
                if not will_retry:
                    raise
            finally:
                stop_event.set()
                t.join()
                print()  # newline when done
        raise AssertionError("Retry loop exited without response or exception.")


class OpenAiLlmClient(AbstractLlmClient):
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
        response = self._post_with_retries(rendered_request)
        payload = response.json()

        try:
            return payload["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as exc:
            raise OpenAiLlmResponseError(
                "Missing OpenAI chat completion response content."
            ) from exc

    def _post_with_retries(self, rendered_request: RenderedTranslatorRequest) -> httpx.Response:
        max_attempt_count = rendered_request.profile.max_retries + 1
        for attempt_index in range(max_attempt_count):
            started_at = perf_counter()
            stop_event = threading.Event()
            t = threading.Thread(target=progress_dots, args=(stop_event,), daemon=True)
            try:
                t.start()
                print(f"OpenAiLlmClient call in progress: profile={rendered_request.profile_name} attempt={attempt_index + 1} : ",end="\n", flush=True)
                response = self._http_client.post(
                    _build_openai_chat_url(rendered_request.profile.url),
                    headers=_build_headers(rendered_request.profile),
                    json={
                        "model": rendered_request.profile.model,
                        "messages": [
                            {"role": message.role, "content": message.content}
                            for message in rendered_request.messages
                        ],
                        "temperature": rendered_request.profile.temperature,
                    },
                    timeout=rendered_request.profile.timeout_seconds,
                )
                response.raise_for_status()
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                self._logger.info(
                    "LLM call completed: profile=%s attempt=%s elapsed_seconds=%.3f http_status_code=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    response.status_code,
                )
                return response
            except httpx.TimeoutException:
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                will_retry = attempt_index < rendered_request.profile.max_retries
                self._logger.warning(
                    "LLM call failed: profile=%s attempt=%s elapsed_seconds=%.3f error_category=timeout will_retry=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    will_retry,
                )
                if not will_retry:
                    raise
            except httpx.HTTPStatusError as exc:
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                will_retry = (
                    attempt_index < rendered_request.profile.max_retries
                    and exc.response.status_code >= 500
                )
                self._logger.warning(
                    "LLM call failed: profile=%s attempt=%s elapsed_seconds=%.3f error_category=http_status http_status_code=%s will_retry=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    exc.response.status_code,
                    will_retry,
                )
                if not will_retry or exc.response.status_code < 500:
                    raise
            except httpx.RequestError:
                elapsed_seconds = perf_counter() - started_at
                self._record_attempt_duration(elapsed_seconds)
                will_retry = attempt_index < rendered_request.profile.max_retries
                self._logger.warning(
                    "LLM call failed: profile=%s attempt=%s elapsed_seconds=%.3f error_category=request_error will_retry=%s",
                    rendered_request.profile_name,
                    attempt_index + 1,
                    elapsed_seconds,
                    will_retry,
                )
                if not will_retry:
                    raise
            finally:
                stop_event.set()
                t.join()
                print()  # newline when done
        raise AssertionError("Retry loop exited without response or exception.")


def build_llm_client(api: str, http_client: httpx.Client | None = None) -> AbstractLlmClient:
    if api == "ollama":
        return OllamaLlmClient(http_client=http_client)
    if api == "openai":
        return OpenAiLlmClient(http_client=http_client)
    raise UnsupportedLlmProviderError(f"Unsupported LLM API provider: {api}")

def _build_headers(profile: TranslatorProfileConfig) -> dict[str, str]:
    if profile.credential is None:
        return {}
    return {"Authorization": f"Bearer {profile.credential}"}


def _build_chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/api/chat"


def _build_openai_chat_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"