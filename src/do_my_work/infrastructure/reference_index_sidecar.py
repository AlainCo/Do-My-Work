from pathlib import Path
from datetime import datetime

import yaml

from do_my_work.domain.models import ReferenceIndexSidecar


def load_reference_index_sidecar(path: Path) -> ReferenceIndexSidecar:
    if not path.exists():
        return ReferenceIndexSidecar()

    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}

    urls = data.get("urls")
    if isinstance(urls, list):
        for entry in urls:
            if not isinstance(entry, dict):
                continue
            last_checked_at = entry.get("last_checked_at")
            if isinstance(last_checked_at, datetime):
                entry["last_checked_at"] = last_checked_at.isoformat().replace("+00:00", "Z")

    return ReferenceIndexSidecar.model_validate(data)


def write_reference_index_sidecar(path: Path, sidecar: ReferenceIndexSidecar) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(
            sidecar.model_dump(mode="python", exclude_none=True),
            stream,
            sort_keys=False,
            allow_unicode=False,
        )