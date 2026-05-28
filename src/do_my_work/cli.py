from pathlib import Path
from typing import Annotated

import typer

from do_my_work.application.batch_runner import BatchRunner
from do_my_work.domain.models import HelloJobConfig
from do_my_work.infrastructure.config_loader import load_hello_job_config
from do_my_work.shared.logging_config import configure_logging

app = typer.Typer(help="Do My Work batch command line interface.")


@app.callback()
def main() -> None:
    """Batch command group."""


@app.command()
def hello(
    config: Annotated[Path | None, typer.Option(help="Path to a YAML config file.")] = None,
) -> None:
    """Run the trivial hello batch."""
    configure_logging()
    job_config = load_hello_job_config(config) if config else HelloJobConfig()
    result = BatchRunner().run(job_config)
    typer.echo(result.message)


if __name__ == "__main__":
    app()