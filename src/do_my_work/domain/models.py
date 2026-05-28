from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_dir: Path = Field(default=Path("work/input"))
    output_dir: Path = Field(default=Path("work/output"))
    data_dir: Path = Field(default=Path("work/data"))


class BatchRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    workspace: WorkspaceConfig


class TaskStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DiscoverFilesTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_files"] = "discover_files"
    root: Path = Field(default=Path("."))


class CopyFileTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["copy_file"] = "copy_file"
    relative_path: Path
    source_digest: str


TaskSpec = Annotated[
    DiscoverFilesTaskSpec | CopyFileTaskSpec,
    Field(discriminator="kind"),
]


class TaskOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    created_task_keys: list[str] = Field(default_factory=list)
    error: str | None = None


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_key: str
    spec: TaskSpec
    status: TaskStatus = TaskStatus.PENDING
    child_task_keys: list[str] = Field(default_factory=list)
    outcome: TaskOutcome | None = None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    request_kind: Literal["copy_tree"] = "copy_tree"
    root: Path = Field(default=Path("."))
    status: Literal["pending", "running", "succeeded", "failed"] = "pending"
    root_task_key: str