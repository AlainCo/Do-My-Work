import json
from pathlib import Path

from do_my_work.domain.models import RunRequest, TaskRecord


class JsonTaskRepository:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def get(self, task_key: str) -> TaskRecord | None:
        path = self._build_path(task_key)
        if not path.exists():
            return None
        return TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def list_all(self) -> list[TaskRecord]:
        if not self._directory.exists():
            return []
        return [
            TaskRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in sorted(self._directory.glob("*.json"))
        ]

    def save(self, record: TaskRecord) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._build_path(record.task_key)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")

    def _build_path(self, task_key: str) -> Path:
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