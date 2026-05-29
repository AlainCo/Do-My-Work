from hashlib import sha256
from pathlib import Path


def make_discover_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_documents", root.as_posix())


def make_discover_summary_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_summary_documents", root.as_posix())


def make_copy_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("copy", relative_path.as_posix(), source_digest)


def make_discover_document_fragments_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key(
        "discover_document_fragments",
        relative_path.as_posix(),
        source_digest,
    )


def make_process_fragment_task_key(document_relative_path: Path, fragment_digest: str) -> str:
    return _make_task_key(
        "process_fragment",
        document_relative_path.as_posix(),
        fragment_digest,
    )


def make_merge_fragment_results_task_key(
    document_relative_path: Path,
    source_digest: str,
    header_text: str = "# Fragment Length Report",
    footer_text: str | None = None,
) -> str:
    return _make_task_key(
        "merge_fragment_results",
        document_relative_path.as_posix(),
        source_digest,
        header_text,
        footer_text or "",
    )


def make_summarize_markdown_document_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("summarize_markdown_document", relative_path.as_posix(), source_digest)


def _make_task_key(kind: str, *parts: str) -> str:
    payload = "|".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"task:{kind}:{digest}"