from hashlib import sha256
from pathlib import Path

from do_my_work.domain.models import TranslatorProfileConfig


def make_discover_reference_documents_task_key(root: Path) -> str:
    return _make_task_key("discover_reference_documents", root.as_posix())


def make_discover_translate_documents_task_key(
    root: Path,
    profile_name: str,
    profile_digest: str,
    render_digest: str | None = None,
) -> str:
    parts = [root.as_posix(), profile_name, profile_digest]
    if render_digest:
        parts.append(render_digest)
    return _make_task_key("discover_translate_documents", *parts)


def make_discover_translate_document_fragments_task_key(
    relative_path: Path,
    source_digest: str,
    profile_name: str,
    profile_digest: str,
    render_digest: str | None = None,
) -> str:
    parts = [relative_path.as_posix(), source_digest, profile_name, profile_digest]
    if render_digest:
        parts.append(render_digest)
    return _make_task_key("discover_translate_document_fragments", *parts)


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


def make_merge_translated_fragments_task_key(
    document_relative_path: Path,
    source_digest: str,
    profile_name: str,
    profile_digest: str,
    render_digest: str | None = None,
) -> str:
    parts = [document_relative_path.as_posix(), source_digest, profile_name, profile_digest]
    if render_digest:
        parts.append(render_digest)
    return _make_task_key("merge_translated_fragments", *parts)


def make_index_markdown_references_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("index_markdown_references", relative_path.as_posix(), source_digest)


def make_merge_reference_indexes_task_key(root: Path, relative_paths: list[Path]) -> str:
    return _make_task_key(
        "merge_reference_indexes",
        root.as_posix(),
        *(relative_path.as_posix() for relative_path in relative_paths),
    )


def make_translator_profile_digest(profile: TranslatorProfileConfig) -> str:
    payload = "|".join(
        [
            profile.model,
            str(profile.temperature),
            profile.system_prompt,
            profile.user_prompt,
        ]
    )
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


def make_translated_document_render_digest(
    profile: TranslatorProfileConfig,
) -> str | None:
    if not profile.translated_document_header and not profile.translated_document_footer:
        return None

    payload = "|".join(
        [
            profile.translated_document_header or "",
            profile.translated_document_footer or "",
        ]
    )
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


def _make_task_key(kind: str, *parts: str) -> str:
    payload = "|".join(parts)
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"task:{kind}:{digest}"