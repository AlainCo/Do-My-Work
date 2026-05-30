from pathlib import Path

import yaml

from do_my_work.domain.models import LocalWorkflowConfig, WorkspaceConfig

LOCAL_WORKFLOW_CONFIG_NAME = "do-my-work.yaml"


def _load_yaml_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def load_workspace_config(path: Path) -> WorkspaceConfig:
    data = _load_yaml_file(path)
    return WorkspaceConfig.model_validate(data)


def load_local_workflow_config(path: Path) -> LocalWorkflowConfig:
    data = _load_yaml_file(path)
    return LocalWorkflowConfig.model_validate(data)