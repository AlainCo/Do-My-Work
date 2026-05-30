from pathlib import Path
from typing import Annotated
from typing import Literal

import typer

from do_my_work.application.batch_runner import BatchRunner
from do_my_work.domain.models import RunRequest, WorkspaceConfig, WorkflowRunSummary
from do_my_work.infrastructure.config_loader import load_workspace_config
from do_my_work.infrastructure.json_workflow_store import JsonRunRepository
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


def _format_delta(old_value: int | float, new_value: int | float, precision: int = 0) -> str:
    delta = new_value - old_value
    if precision == 0:
        return f"{new_value} ({delta:+.0f})"
    return f"{new_value:.{precision}f} ({delta:+.{precision}f})"


def _echo_run_comparison(older_run: RunRequest, newer_run: RunRequest) -> None:
    typer.echo(f"Comparing runs: {older_run.run_id} -> {newer_run.run_id}")
    typer.echo(f"Request kind: {older_run.request_kind} -> {newer_run.request_kind}")
    typer.echo(f"Root: {older_run.root} -> {newer_run.root}")
    typer.echo(f"Status: {older_run.status} -> {newer_run.status}")

    older_summary = older_run.summary
    newer_summary = newer_run.summary
    if older_summary is None or newer_summary is None:
        typer.echo("Run summary comparison unavailable: one of the selected runs has no persisted summary.")
        return

    typer.echo("Summary deltas:")
    _echo_summary_delta("Tasks executed", older_summary.executed_task_count, newer_summary.executed_task_count)
    _echo_summary_delta("Tasks replayed", older_summary.replayed_task_count, newer_summary.replayed_task_count)
    _echo_summary_delta(
        "Failed tasks retried",
        older_summary.retried_failed_task_count,
        newer_summary.retried_failed_task_count,
    )
    _echo_summary_delta("Tasks created", older_summary.created_task_count, newer_summary.created_task_count)
    _echo_summary_delta("Tasks unchanged", older_summary.unchanged_task_count, newer_summary.unchanged_task_count)
    _echo_summary_delta("Pending tasks", older_summary.pending_task_count, newer_summary.pending_task_count)
    _echo_summary_delta("Waiting tasks", older_summary.waiting_task_count, newer_summary.waiting_task_count)
    _echo_summary_delta("Succeeded tasks", older_summary.succeeded_task_count, newer_summary.succeeded_task_count)
    _echo_summary_delta("Failed tasks", older_summary.failed_task_count, newer_summary.failed_task_count)
    _echo_summary_delta(
        "LLM call attempts",
        older_summary.llm_call_attempt_count,
        newer_summary.llm_call_attempt_count,
    )
    _echo_summary_delta(
        "LLM avg seconds",
        older_summary.llm_call_average_seconds,
        newer_summary.llm_call_average_seconds,
        precision=3,
    )
    _echo_summary_delta(
        "LLM variance seconds",
        older_summary.llm_call_variance_seconds,
        newer_summary.llm_call_variance_seconds,
        precision=3,
    )


def _echo_summary_delta(label: str, old_value: int | float, new_value: int | float, precision: int = 0) -> None:
    typer.echo(f"- {label}: {_format_delta(old_value, new_value, precision=precision)}")


def _resolve_runs_for_comparison(
    run_repository: JsonRunRepository,
    older_run_id: str | None,
    newer_run_id: str | None,
    request_kind: Literal["reference_index_tree", "translate_document_tree"] | None,
) -> tuple[RunRequest, RunRequest]:
    if (older_run_id is None) != (newer_run_id is None):
        raise typer.BadParameter("Provide both --older-run-id and --newer-run-id, or neither.")

    if older_run_id is not None and newer_run_id is not None:
        older_run = run_repository.get(older_run_id)
        if older_run is None:
            raise typer.BadParameter(f"Run not found: {older_run_id}")
        newer_run = run_repository.get(newer_run_id)
        if newer_run is None:
            raise typer.BadParameter(f"Run not found: {newer_run_id}")
        if request_kind is not None and (
            older_run.request_kind != request_kind or newer_run.request_kind != request_kind
        ):
            raise typer.BadParameter(
                f"Selected runs do not both match request kind: {request_kind}"
            )
        if older_run.request_kind != newer_run.request_kind:
            raise typer.BadParameter(
                "Selected runs have different request kinds; compare runs of the same workflow type."
            )
        return older_run, newer_run

    run_requests = sorted(run_repository.list_all(), key=lambda run: run.run_id)
    if request_kind is not None:
        run_requests = [run for run in run_requests if run.request_kind == request_kind]
        if len(run_requests) < 2:
            raise typer.BadParameter(
                f"At least two persisted runs are required for request kind: {request_kind}"
            )
        return run_requests[-2], run_requests[-1]

    if len(run_requests) < 2:
        raise typer.BadParameter("At least two persisted runs are required for comparison.")

    newer_run = run_requests[-1]
    for older_run in reversed(run_requests[:-1]):
        if older_run.request_kind == newer_run.request_kind:
            return older_run, newer_run

    raise typer.BadParameter(
        f"No earlier persisted run found for request kind: {newer_run.request_kind}"
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


@app.command("compare-runs")
def compare_runs(
    config: Annotated[Path | None, typer.Option(help="Path to a YAML config file.")] = None,
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Data directory containing persisted workflow run JSON files."),
    ] = None,
    older_run_id: Annotated[
        str | None,
        typer.Option(help="Older run id to compare. If omitted, the second latest run is used."),
    ] = None,
    newer_run_id: Annotated[
        str | None,
        typer.Option(help="Newer run id to compare. If omitted, the latest run is used."),
    ] = None,
    request_kind: Annotated[
        Literal["reference_index_tree", "translate_document_tree"] | None,
        typer.Option(
            help=(
                "Restrict comparison to one workflow type. By default, compare-runs uses "
                "the latest run and the previous run of the same request kind."
            )
        ),
    ] = None,
) -> None:
    """Compare two persisted workflow runs using their saved summaries."""
    configure_logging()
    workspace_config = _resolve_workspace_config(config=config, data_dir=data_dir)
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    run_repository = JsonRunRepository(workspace_config.data_dir / "runs")
    older_run, newer_run = _resolve_runs_for_comparison(
        run_repository,
        older_run_id,
        newer_run_id,
        request_kind,
    )
    _echo_run_comparison(older_run, newer_run)


if __name__ == "__main__":
    app()