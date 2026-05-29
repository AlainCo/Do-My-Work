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


@app.command()
def hello(
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
) -> None:
    """Run the trivial batch entry point with workspace settings."""
    configure_logging()
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
    workspace_config = workspace_config.model_copy(update=overrides)
    result = BatchRunner().run(workspace_config)
    typer.echo(result.message)
    typer.echo(f"Input directory: {result.workspace.input_dir}")
    typer.echo(f"Output directory: {result.workspace.output_dir}")
    typer.echo(f"Data directory: {result.workspace.data_dir}")


@app.command("copy-tree")
def copy_tree(
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
    """Copy Markdown documents from the requested input subtree while persisting workflow state."""
    configure_logging()
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
    workspace_config = workspace_config.model_copy(update=overrides)
    typer.echo(f"Input directory: {workspace_config.input_dir}")
    typer.echo(f"Output directory: {workspace_config.output_dir}")
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    run_result = BatchRunner().run_copy_tree(workspace_config, root=root)
    typer.echo(f"Workflow run completed: {run_result.run_id}")
    typer.echo(f"Tasks executed: {run_result.summary.executed_task_count}")
    typer.echo(f"Tasks replayed: {run_result.summary.replayed_task_count}")
    typer.echo(f"Tasks created: {run_result.summary.created_task_count}")
    typer.echo(f"Tasks unchanged: {run_result.summary.unchanged_task_count}")


@app.command("summary-document-tree")
def summary_document_tree(
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
    """Summarize Markdown documents from the requested input subtree."""
    configure_logging()
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
    workspace_config = workspace_config.model_copy(update=overrides)
    typer.echo(f"Input directory: {workspace_config.input_dir}")
    typer.echo(f"Output directory: {workspace_config.output_dir}")
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    run_result = BatchRunner().run_summary_document_tree(workspace_config, root=root)
    typer.echo(f"Workflow run completed: {run_result.run_id}")
    typer.echo(f"Tasks executed: {run_result.summary.executed_task_count}")
    typer.echo(f"Tasks replayed: {run_result.summary.replayed_task_count}")
    typer.echo(f"Tasks created: {run_result.summary.created_task_count}")
    typer.echo(f"Tasks unchanged: {run_result.summary.unchanged_task_count}")


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
    workspace_config = workspace_config.model_copy(update=overrides)
    typer.echo(f"Input directory: {workspace_config.input_dir}")
    typer.echo(f"Output directory: {workspace_config.output_dir}")
    typer.echo(f"Data directory: {workspace_config.data_dir}")
    run_result = BatchRunner().run_translate_document_tree(
        workspace_config,
        root=root,
        translator_profile=translator_profile,
    )
    typer.echo(f"Workflow run completed: {run_result.run_id}")
    typer.echo(f"Tasks executed: {run_result.summary.executed_task_count}")
    typer.echo(f"Tasks replayed: {run_result.summary.replayed_task_count}")
    typer.echo(f"Tasks created: {run_result.summary.created_task_count}")
    typer.echo(f"Tasks unchanged: {run_result.summary.unchanged_task_count}")


if __name__ == "__main__":
    app()