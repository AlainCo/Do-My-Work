from pathlib import Path

import yaml

from do_my_work.domain.models import HelloJobConfig


def load_hello_job_config(path: Path) -> HelloJobConfig:
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    return HelloJobConfig.model_validate(data)