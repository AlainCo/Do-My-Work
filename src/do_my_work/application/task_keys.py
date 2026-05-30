from hashlib import sha256
from pathlib import Path

from do_my_work.domain.models import TranslatorProfileConfig


def make_discover_reference_documents_task_key(
    root: Path,
    local_policy_digest: str | None = None,
) -> str:
    parts = [root.as_posix()]
    if local_policy_digest:
        parts.append(local_policy_digest)
    return _make_task_key("discover_reference_documents", *parts)


def make_discover_translate_documents_task_key(
    root: Path,
    profile_name: str,
    profile_digest: str,
    plan_digest: str | None = None,
    render_digest: str | None = None,
    local_policy_digest: str | None = None,
) -> str:
    parts = [root.as_posix(), profile_name, profile_digest]
    if plan_digest:
        parts.append(plan_digest)
    if render_digest:
        parts.append(render_digest)
    if local_policy_digest:
        parts.append(local_policy_digest)
    return _make_task_key("discover_translate_documents", *parts)


def make_discover_translate_document_fragments_task_key(
    relative_path: Path,
    source_digest: str,
    profile_name: str,
    profile_digest: str,
    plan_digest: str | None = None,
    render_digest: str | None = None,
) -> str:
    parts = [relative_path.as_posix(), source_digest, profile_name, profile_digest]
    if plan_digest:
        parts.append(plan_digest)
    if render_digest:
        parts.append(render_digest)
    return _make_task_key("discover_translate_document_fragments", *parts)


def make_translate_fragment_task_key(
    document_relative_path: Path,
    fragment_digest: str,
    profile_name: str,
    profile_digest: str,
) -> str:
    document_scope = _make_key_digest(document_relative_path.as_posix())
    return _make_scoped_task_key(
        "translate_fragment",
        document_scope,
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
    plan_digest: str | None = None,
    render_digest: str | None = None,
) -> str:
    parts = [document_relative_path.as_posix(), source_digest, profile_name, profile_digest]
    if plan_digest:
        parts.append(plan_digest)
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


def make_translation_plan_digest(profile: TranslatorProfileConfig) -> str | None:
    if (
        profile.max_pre_context_bytes <= 0
        and profile.max_post_context_bytes <= 0
        and profile.max_total_text_bytes <= 0
        and profile.max_input_fragment_bytes <= 0
    ):
        return None

    payload = "|".join(
        [
            str(profile.max_pre_context_bytes),
            str(profile.max_post_context_bytes),
            str(profile.max_total_text_bytes),
            str(profile.max_input_fragment_bytes),
        ]
    )
    return f"sha256:{sha256(payload.encode('utf-8')).hexdigest()}"


def _make_task_key(kind: str, *parts: str) -> str:
    digest = _make_key_digest(*parts)
    return f"task:{kind}:{digest}"


def _make_scoped_task_key(kind: str, scope: str, *parts: str) -> str:
    digest = _make_key_digest(*parts)
    return f"task:{kind}:{scope}:{digest}"


def _make_key_digest(*parts: str) -> str:
    payload = "|".join(parts)
    return sha256(payload.encode("utf-8")).hexdigest()[:12]