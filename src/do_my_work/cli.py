from pathlib import Path
from typing import Annotated

import typer

from do_my_work.application.batch_runner import BatchRunner
from do_my_work.domain.models import WorkspaceConfig
from do_my_work.infrastructure.config_loader import load_workspace_config
from do_my_work.shared.logging_config import configure_logging

app = typer.Typer(help="Do My Work batch command line interface.")


@app.callback()
def main() -> None:
    """Batch command group."""


def _resolve_workspace_config(
    config: Path | None,
    input_dir: Path | None = None,
    output_dir: Path | None = None,
    data_dir: Path | None = None,
) -> WorkspaceConfig:
    workspace_config = load_workspace_config(config) if config else WorkspaceConfig()
    overrides = {
        key: value
        for key, value in {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "data_dir": data_dir,
        }.items()
        if value is not None
    }
    return workspace_config.model_copy(update=overrides)


def _echo_run_summary(run_result) -> None:
    typer.echo(f"Workflow run completed: {run_result.run_id}")
    typer.echo(f"Tasks executed: {run_result.summary.executed_task_count}")
    typer.echo(f"Tasks replayed: {run_result.summary.replayed_task_count}")
    typer.echo(f"Failed tasks retried: {run_result.summary.retried_failed_task_count}")
    typer.echo(f"Tasks created: {run_result.summary.created_task_count}")
    typer.echo(f"Tasks unchanged: {run_result.summary.unchanged_task_count}")
    typer.echo(
        "Active task states: "
        f"pending={run_result.summary.pending_task_count} "
        f"waiting={run_result.summary.waiting_task_count} "
        f"succeeded={run_result.summary.succeeded_task_count} "
        f"failed={run_result.summary.failed_task_count}"
    )
    typer.echo(
        "LLM call timings: "
        f"attempts={run_result.summary.llm_call_attempt_count} "
        f"avg_seconds={run_result.summary.llm_call_average_seconds:.3f} "
        f"variance_seconds={run_result.summary.llm_call_variance_seconds:.3f}"
    )


@app.command("reference-index-tree")
def reference_index_tree(
    config: Annotated[Path | None, typer.Option(help="Path to a YAML config file.")] = None,
    input_dir: Annotated[
        Path | None,
        typer.Option(help="Input directory for source documents."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(help="Output directory for generated documents."),
    ] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Data directory for state and intermediate artifacts."),
    ] = None,
    root: Annotated[
        Path,
        typer.Option(help="Relative subtree under the input directory to process."),
    ] = Path("."),
) -> None:
    """Index Markdown references from the requested input subtree."""
    configure_logging()
    workspace_config = _resolve_workspace_config(config, input_dir, output_dir, data_dir)
    typer.echo(f"Input directory: {workspace_config.input_dir}")
    typer.echo(f"Output directory: {workspace_config.output_dir}")
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    run_result = BatchRunner().run_reference_index_tree(workspace_config, root=root)
    _echo_run_summary(run_result)


@app.command("translate-document-tree")
def translate_document_tree(
    config: Annotated[Path | None, typer.Option(help="Path to a YAML config file.")] = None,
    input_dir: Annotated[
        Path | None,
        typer.Option(help="Input directory for source documents."),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(help="Output directory for generated documents."),
    ] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Data directory for state and intermediate artifacts."),
    ] = None,
    root: Annotated[
        Path,
        typer.Option(help="Relative subtree under the input directory to process."),
    ] = Path("."),
    translator_profile: Annotated[
        str,
        typer.Option(help="Translator profile name under llm.translator in the YAML config."),
    ] = "technical",
) -> None:
    """Translate Markdown documents through fragment tasks using a named LLM profile."""
    configure_logging()
    workspace_config = _resolve_workspace_config(config, input_dir, output_dir, data_dir)
    typer.echo(f"Input directory: {workspace_config.input_dir}")
    typer.echo(f"Output directory: {workspace_config.output_dir}")
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    run_result = BatchRunner().run_translate_document_tree(
        workspace_config,
        root=root,
        translator_profile=translator_profile,
    )
    _echo_run_summary(run_result)


@app.command("clean-tasks")
def clean_tasks(
    config: Annotated[Path | None, typer.Option(help="Path to a YAML config file.")] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Data directory containing workflow state and task files."),
    ] = None,
) -> None:
    """Remove persisted workflow task JSON data from the workspace data directory."""
    configure_logging()
    workspace_config = _resolve_workspace_config(config=config, data_dir=data_dir)
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    removed_task_count = BatchRunner().clean_tasks(workspace_config)
    typer.echo(f"Task files removed: {removed_task_count}")


if __name__ == "__main__":
    app()