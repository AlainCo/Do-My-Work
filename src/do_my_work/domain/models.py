from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

FragmentKind = Literal[
    "heading",
    "paragraph",
    "list_item",
    "blockquote",
    "code_block",
    "mermaid",
]


class WorkspaceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_dir: Path = Field(default=Path("work/input"))
    output_dir: Path = Field(default=Path("work/output"))
    data_dir: Path = Field(default=Path("work/data"))


class BatchRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    workspace: WorkspaceConfig


class WorkflowRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executed_task_count: int = 0
    replayed_task_count: int = 0
    created_task_count: int = 0
    unchanged_task_count: int = 0


class MarkdownFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragment_kind: FragmentKind
    heading_path: list[str] = Field(default_factory=list)
    text: str
    length: int


class TaskStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DiscoverDocumentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_documents"] = "discover_documents"
    root: Path = Field(default=Path("."))


class DiscoverSummaryDocumentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_summary_documents"] = "discover_summary_documents"
    root: Path = Field(default=Path("."))


class CopyFileTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["copy_file"] = "copy_file"
    relative_path: Path
    source_digest: str


class SummarizeMarkdownDocumentTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["summarize_markdown_document"] = "summarize_markdown_document"
    relative_path: Path
    source_digest: str


class DiscoverDocumentFragmentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_document_fragments"] = "discover_document_fragments"
    relative_path: Path
    source_digest: str


class ProcessFragmentTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["process_fragment"] = "process_fragment"
    document_relative_path: Path
    fragment_kind: FragmentKind
    heading_path: list[str] = Field(default_factory=list)
    text: str
    fragment_digest: str


class MergeFragmentResultsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["merge_fragment_results"] = "merge_fragment_results"
    document_relative_path: Path
    source_digest: str
    fragment_task_keys: list[str] = Field(default_factory=list)
    header_text: str = "# Fragment Length Report"
    footer_text: str | None = None


TaskSpec = Annotated[
    DiscoverDocumentsTaskSpec
    | DiscoverSummaryDocumentsTaskSpec
    | CopyFileTaskSpec
    | SummarizeMarkdownDocumentTaskSpec
    | DiscoverDocumentFragmentsTaskSpec
    | ProcessFragmentTaskSpec
    | MergeFragmentResultsTaskSpec,
    Field(discriminator="kind"),
]


class ProcessedFragmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["processed_fragment"] = "processed_fragment"
    rendered_text: str
    length: int


class TaskOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    created_task_keys: list[str] = Field(default_factory=list)
    error: str | None = None
    result: ProcessedFragmentResult | None = None


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
    request_kind: Literal["copy_tree", "summary_document_tree"] = "copy_tree"
    root: Path = Field(default=Path("."))
    status: Literal["pending", "running", "succeeded", "failed"] = "pending"
    root_task_key: str


class WorkflowRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_request: RunRequest
    summary: WorkflowRunSummary

    @property
    def run_id(self) -> str:
        return self.run_request.run_id

    @property
    def status(self) -> str:
        return self.run_request.status