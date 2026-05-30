import json
from pathlib import Path

from do_my_work.domain.models import RunRequest, TaskRecord


class JsonTaskRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get(self, task_key: str) -> TaskRecord | None:
        path = self._build_path(task_key)
        if not path.exists():
            legacy_path = self._build_legacy_path(task_key)
            if not legacy_path.exists():
                return None
            path = legacy_path
        return TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list_all(self) -> list[TaskRecord]:
        if not self._directory.exists():
            return []
        return [
            TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._directory.rglob("*.json"))
        ]

    def save(self, record: TaskRecord) -> None:
        path = self._build_path(record.task_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    def _build_path(self, task_key: str) -> Path:
        return self._directory / _task_kind_directory_name(task_key) / f"{_safe_file_name(task_key)}.json"

    def _build_legacy_path(self, task_key: str) -> Path:
        return self._directory / f"{_safe_file_name(task_key)}.json"


class JsonRunRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, run_request: RunRequest) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{_safe_file_name(run_request.run_id)}.json"
        path.write_text(run_request.model_dump_json(indent=2), encoding="utf-8")


def _safe_file_name(value: str) -> str:
    return value.replace(":", "__").replace("/", "__")


def _task_kind_directory_name(task_key: str) -> str:
    parts = task_key.split(":", 2)
    if len(parts) < 3 or parts[0] != "task" or not parts[1]:
        raise ValueError(f"Invalid task key: {task_key}")
    return _safe_file_name(parts[1])