from pathlib import Path

import yaml

from do_my_work.domain.models import WorkspaceConfig


def load_workspace_config(path: Path) -> WorkspaceConfig:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    return WorkspaceConfig.model_validate(data)