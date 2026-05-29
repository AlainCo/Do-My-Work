import pytest

from tests.support.ollama_mock_behavior import MockChatMessage, RuleBasedOllamaMockBehavior
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


def test_create_app_explains_how_to_install_fastapi_when_missing() -> None:
    with pytest.raises(RuntimeError, match="mock-ollama"):
        create_app()