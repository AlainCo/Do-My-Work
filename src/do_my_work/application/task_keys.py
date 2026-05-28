from hashlib import sha256
from pathlib import Path


def make_discover_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_documents", root.as_posix())


def make_discover_summary_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_summary_documents", root.as_posix())


def make_copy_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("copy", relative_path.as_posix(), source_digest)


def make_summarize_markdown_document_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("summarize_markdown_document", relative_path.as_posix(), source_digest)


def _make_task_key(kind: str, *parts: str) -> str:
    payload = "|".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"task:{kind}:{digest}"