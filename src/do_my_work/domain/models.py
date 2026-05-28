from pathlib import Path

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