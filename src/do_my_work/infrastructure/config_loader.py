from pathlib import Path

import yaml
from pydantic import ValidationError

from do_my_work.domain.models import LocalWorkflowConfig, WorkspaceConfig

LOCAL_WORKFLOW_CONFIG_NAME = "do-my-work.yaml"


class ConfigLoadError(ValueError):
    def __init__(self, path: Path, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


def _format_validation_error(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
        details.append(f"{location}: {error.get('msg', 'Invalid value.')}")
    return "; ".join(details)


def _load_yaml_file(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream) or {}
    except FileNotFoundError as exc:
        raise ConfigLoadError(path, f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigLoadError(path, f"Invalid YAML in {path}: {exc}") from exc


def load_workspace_config(path: Path) -> WorkspaceConfig:
    data = _load_yaml_file(path)
    try:
        return WorkspaceConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigLoadError(path, f"Invalid configuration in {path}: {_format_validation_error(exc)}") from exc


def load_local_workflow_config(path: Path) -> LocalWorkflowConfig:
    data = _load_yaml_file(path)
    try:
        return LocalWorkflowConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigLoadError(path, f"Invalid configuration in {path}: {_format_validation_error(exc)}") from exc