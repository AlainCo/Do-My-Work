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
    """Copy the requested input subtree while persisting workflow state."""
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
    run_id = BatchRunner().run_copy_tree(workspace_config, root=root)
    typer.echo(f"Workflow run completed: {run_id}")
    typer.echo(f"Input directory: {workspace_config.input_dir}")
    typer.echo(f"Output directory: {workspace_config.output_dir}")
    typer.echo(f"Data directory: {workspace_config.data_dir}")


if __name__ == "__main__":
    app()