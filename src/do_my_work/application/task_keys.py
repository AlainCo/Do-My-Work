from hashlib import sha256
from pathlib import Path

from do_my_work.domain.models import TranslatorProfileConfig


def make_discover_reference_documents_task_key(
    root: Path,
    local_policy_digest: str | None = None,
    check_urls: bool = False,
    url_check_run_token: str | None = None,
) -> str:
    parts = [root.as_posix()]
    if local_policy_digest:
        parts.append(local_policy_digest)
    if check_urls:
        parts.append("check_urls")
        if url_check_run_token:
            parts.append(url_check_run_token)
    return _make_task_key("discover_reference_documents", *parts)


def make_discover_copy_resources_task_key(
    root: Path,
    local_policy_digest: str | None = None,
) -> str:
    parts = [root.as_posix()]
    if local_policy_digest:
        parts.append(local_policy_digest)
    return _make_task_key("discover_copy_resources", *parts)


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
    translation_hints_digest: str | None = None,
) -> str:
    parts = [relative_path.as_posix(), source_digest, profile_name, profile_digest]
    if plan_digest:
        parts.append(plan_digest)
    if render_digest:
        parts.append(render_digest)
    if translation_hints_digest:
        parts.append(translation_hints_digest)
    return _make_task_key("discover_translate_document_fragments", *parts)


def make_translate_fragment_task_key(
    document_relative_path: Path,
    fragment_digest: str,
    profile_name: str,
    profile_digest: str,
    translation_hints_digest: str | None = None,
) -> str:
    document_scope = _make_key_digest(document_relative_path.as_posix())
    parts = [
        document_relative_path.as_posix(),
        fragment_digest,
        profile_name,
        profile_digest,
    ]
    if translation_hints_digest:
        parts.append(translation_hints_digest)
    return _make_scoped_task_key("translate_fragment", document_scope, *parts)


def make_merge_translated_fragments_task_key(
    document_relative_path: Path,
    source_digest: str,
    profile_name: str,
    profile_digest: str,
    plan_digest: str | None = None,
    render_digest: str | None = None,
    translation_hints_digest: str | None = None,
) -> str:
    parts = [document_relative_path.as_posix(), source_digest, profile_name, profile_digest]
    if plan_digest:
        parts.append(plan_digest)
    if render_digest:
        parts.append(render_digest)
    if translation_hints_digest:
        parts.append(translation_hints_digest)
    return _make_task_key("merge_translated_fragments", *parts)


def make_index_markdown_references_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("index_markdown_references", relative_path.as_posix(), source_digest)


def make_check_reference_url_task_key(url: str, url_check_run_token: str | None = None) -> str:
    parts = [url]
    if url_check_run_token:
        parts.append(url_check_run_token)
    return _make_task_key("check_reference_url", *parts)


def make_copy_resource_file_task_key(relative_path: Path, source_digest: str) -> str:
    return _make_task_key("copy_resource_file", relative_path.as_posix(), source_digest)


def make_merge_reference_indexes_task_key(
    root: Path,
    relative_paths: list[Path],
    checked_urls: list[str] | None = None,
    url_check_run_token: str | None = None,
) -> str:
    parts = [root.as_posix(), *(relative_path.as_posix() for relative_path in relative_paths)]
    if checked_urls:
        parts.append("check_urls")
        parts.extend(checked_urls)
        if url_check_run_token:
            parts.append(url_check_run_token)
    return _make_task_key("merge_reference_indexes", *parts)


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
    *,
    with_review: bool = False,
    translated_first: bool = False,
) -> str | None:
    return make_translated_document_render_digest_for_content(
        profile.translated_document_header,
        profile.translated_document_footer,
        with_review=with_review,
        translated_first=translated_first,
    )


def make_translated_document_render_digest_for_content(
    translated_document_header: str | None,
    translated_document_footer: str | None,
    *,
    with_review: bool = False,
    translated_first: bool = False,
) -> str | None:
    if (
        not translated_document_header
        and not translated_document_footer
        and not with_review
    ):
        return None

    payload = "|".join(
        [
            translated_document_header or "",
            translated_document_footer or "",
            "with_review" if with_review else "without_review",
            "translated_first" if translated_first else "original_first",
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