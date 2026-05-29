import importlib.util

import pytest

from tests.support.ollama_mock_behavior import (
    MockChatMessage,
    RuleBasedOllamaMockBehavior,
    TranslatorChatBehavior,
)
from tests.support.ollama_mock_server import create_app


def test_rule_based_ollama_mock_behavior_generate_uses_keyword_response() -> None:
    behavior = RuleBasedOllamaMockBehavior()

    response = behavior.generate(model="mock-llama", prompt="Pourquoi Python ?")

    assert response["model"] == "mock-llama"
    assert response["response"] == "Python est un excellent choix pour prototyper rapidement."
    assert response["done"] is True


def test_rule_based_ollama_mock_behavior_chat_reads_last_user_message() -> None:
    behavior = RuleBasedOllamaMockBehavior()

    response = behavior.chat(
        model="mock-llama",
        messages=[
            MockChatMessage(role="system", content="You are helpful."),
            MockChatMessage(role="user", content="bonjour"),
            MockChatMessage(role="assistant", content="Bonjour."),
            MockChatMessage(role="user", content="Parlons Python."),
        ],
    )

    assert response["model"] == "mock-llama"
    assert response["message"] == {
        "role": "assistant",
        "content": "Python est un excellent choix pour prototyper rapidement.",
    }
    assert response["done"] is True


def test_rule_based_ollama_mock_behavior_chat_translator_mode_uppercases_source_text() -> None:
    behavior = RuleBasedOllamaMockBehavior()

    response = behavior.chat(
        model="mock-llama",
        messages=[
            MockChatMessage(role="system", content="You are a translator."),
            MockChatMessage(
                role="user",
                content=(
                    "Please translate this.\n"
                    "===BEGIN SOURCE TEXT===\n"
                    "Bonjour monde\n"
                    "===END SOURCE TEXT===\n"
                ),
            ),
        ],
    )

    assert response["model"] == "mock-llama"
    assert response["message"] == {
        "role": "assistant",
        "content": "BONJOUR MONDE\n",
    }
    assert response["done"] is True


def test_translator_chat_behavior_matches_translator_system_prompt() -> None:
    chat_behavior = TranslatorChatBehavior()

    assert chat_behavior.matches(
        [MockChatMessage(role="system", content="You are a translator.")]
    )


def test_translator_chat_behavior_extracts_and_uppercases_source_text() -> None:
    chat_behavior = TranslatorChatBehavior()

    assert chat_behavior.render(
        [
            MockChatMessage(role="system", content="You are a translator."),
            MockChatMessage(
                role="user",
                content=(
                    "===BEGIN SOURCE TEXT===\n"
                    "Bonjour monde\n"
                    "===END SOURCE TEXT===\n"
                ),
            ),
        ]
    ) == "BONJOUR MONDE\n"


def test_create_app_explains_how_to_install_fastapi_when_missing() -> None:
    if importlib.util.find_spec("fastapi") is None:
        with pytest.raises(RuntimeError, match="mock-ollama"):
            create_app()
        return

    app = create_app()

    assert app.title == "FastAPI"