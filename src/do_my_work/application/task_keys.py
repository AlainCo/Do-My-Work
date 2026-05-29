from hashlib import sha256
from pathlib import Path

from do_my_work.domain.models import TranslatorProfileConfig


def make_discover_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_documents", root.as_posix())


def make_discover_summary_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_summary_documents", root.as_posix())


def make_discover_reference_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_reference_documents", root.as_posix())


def make_discover_translate_documents_task_key(
    root: Path,
    profile_name: str,
    profile_digest: str,
) -> str:
    return _make_task_key(
        "discover_translate_documents",
        root.as_posix(),
        profile_name,
        profile_digest,
    )


def make_copy_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("copy", relative_path.as_posix(), source_digest)


def make_discover_document_fragments_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key(
        "discover_document_fragments",
        relative_path.as_posix(),
        source_digest,
    )


def make_discover_translate_document_fragments_task_key(
    relative_path: Path,
    source_digest: str,
    profile_name: str,
    profile_digest: str,
) -> str:
    return _make_task_key(
        "discover_translate_document_fragments",
        relative_path.as_posix(),
        source_digest,
        profile_name,
        profile_digest,
    )


def make_process_fragment_task_key(document_relative_path: Path, fragment_digest: str) -> str:
    return _make_task_key(
        "process_fragment",
        document_relative_path.as_posix(),
        fragment_digest,
    )


def make_translate_fragment_task_key(
    document_relative_path: Path,
    fragment_digest: str,
    profile_name: str,
    profile_digest: str,
) -> str:
    return _make_task_key(
        "translate_fragment",
        document_relative_path.as_posix(),
        fragment_digest,
        profile_name,
        profile_digest,
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


def make_merge_translated_fragments_task_key(
    document_relative_path: Path,
    source_digest: str,
    profile_name: str,
    profile_digest: str,
) -> str:
    return _make_task_key(
        "merge_translated_fragments",
        document_relative_path.as_posix(),
        source_digest,
        profile_name,
        profile_digest,
    )


def make_summarize_markdown_document_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("summarize_markdown_document", relative_path.as_posix(), source_digest)


def make_index_markdown_references_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("index_markdown_references", relative_path.as_posix(), source_digest)


def make_translator_profile_digest(profile: TranslatorProfileConfig) -> str:
    payload = "|".join(
        [
            profile.url,
            profile.model,
            str(profile.temperature),
            profile.system_prompt,
            profile.user_prompt,
        ]
    )
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


def _make_task_key(kind: str, *parts: str) -> str:
    payload = "|".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"task:{kind}:{digest}"