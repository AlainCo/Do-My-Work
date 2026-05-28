from do_my_work.application.batch_runner import BatchRunner
from do_my_work.domain.models import HelloJobConfig


def test_batch_runner_builds_expected_message() -> None:
    config = HelloJobConfig(greeting="Bonjour", target="monde")

    result = BatchRunner().run(config)

    assert result.app_name == "Do My Work"
    assert result.message == "Bonjour, monde!"