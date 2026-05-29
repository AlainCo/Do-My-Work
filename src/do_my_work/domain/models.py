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
    llm: "LlmConfig" = Field(default_factory=lambda: LlmConfig())


class TranslatorProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    model: str
    credential: str | None = None
    timeout_seconds: float = Field(default=180.0, gt=0)
    max_retries: int = Field(default=0, ge=0)
    temperature: float = 0.0
    system_prompt: str
    user_prompt: str


class LlmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translator: dict[str, TranslatorProfileConfig] = Field(default_factory=dict)


class WorkflowRunSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executed_task_count: int = 0
    replayed_task_count: int = 0
    retried_failed_task_count: int = 0
    created_task_count: int = 0
    unchanged_task_count: int = 0


class MarkdownFragment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fragment_kind: FragmentKind
    heading_path: list[str] = Field(default_factory=list)
    text: str
    length: int


class MarkdownReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading_path: list[str] = Field(default_factory=list)
    label: str
    url: str


class TaskStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DiscoverReferenceDocumentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_reference_documents"] = "discover_reference_documents"
    root: Path = Field(default=Path("."))


class DiscoverTranslateDocumentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_translate_documents"] = "discover_translate_documents"
    root: Path = Field(default=Path("."))
    profile_name: str
    profile_digest: str


class IndexMarkdownReferencesTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["index_markdown_references"] = "index_markdown_references"
    relative_path: Path
    source_digest: str


class MergeReferenceIndexesTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["merge_reference_indexes"] = "merge_reference_indexes"
    root: Path = Field(default=Path("."))
    document_relative_paths: list[Path] = Field(default_factory=list)
    reference_task_keys: list[str] = Field(default_factory=list)


class DiscoverTranslateDocumentFragmentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["discover_translate_document_fragments"] = (
        "discover_translate_document_fragments"
    )
    relative_path: Path
    source_digest: str
    profile_name: str
    profile_digest: str


class TranslateFragmentTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["translate_fragment"] = "translate_fragment"
    document_relative_path: Path
    fragment_kind: FragmentKind
    heading_path: list[str] = Field(default_factory=list)
    text: str
    fragment_digest: str
    profile_name: str
    profile_digest: str


class MergeTranslatedFragmentsTaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["merge_translated_fragments"] = "merge_translated_fragments"
    document_relative_path: Path
    source_digest: str
    fragment_task_keys: list[str] = Field(default_factory=list)
    profile_name: str
    profile_digest: str


TaskSpec = Annotated[
    DiscoverReferenceDocumentsTaskSpec
    | DiscoverTranslateDocumentsTaskSpec
    | IndexMarkdownReferencesTaskSpec
    | MergeReferenceIndexesTaskSpec
    | DiscoverTranslateDocumentFragmentsTaskSpec
    | TranslateFragmentTaskSpec
    | MergeTranslatedFragmentsTaskSpec,
    Field(discriminator="kind"),
]


class TranslatedFragmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["translated_fragment"] = "translated_fragment"
    translated_text: str
    length: int


class TaskOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    created_task_keys: list[str] = Field(default_factory=list)
    error: str | None = None
    error_category: Literal["timeout", "http_status", "request_error"] | None = None
    result: TranslatedFragmentResult | None = None


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
    request_kind: Literal[
        "reference_index_tree",
        "translate_document_tree",
    ] = "reference_index_tree"
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