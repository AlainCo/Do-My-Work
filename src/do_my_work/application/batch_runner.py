import logging

from do_my_work.domain.models import HelloJobConfig, HelloJobResult


class BatchRunner:
    """Minimal batch orchestrator.

    This is the future home for the workflow coordination logic.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def run(self, config: HelloJobConfig) -> HelloJobResult:
        self._logger.info("Running hello batch for %s", config.target)
        message = f"{config.greeting}, {config.target}!"
        return HelloJobResult(app_name=config.app_name, message=message)