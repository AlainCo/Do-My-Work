import os
from pathlib import Path
import re

import yaml
from pydantic import ValidationError

from do_my_work.domain.models import LocalWorkflowConfig, TranslatorProfileConfig, WorkspaceConfig

LOCAL_WORKFLOW_CONFIG_NAME = "do-my-work.yaml"
ENV_REFERENCE_PATTERN = re.compile(r"^\$\{env:([^}]+)\}$")


class ConfigLoadError(ValueError):
    def __init__(self, path: Path, message: str) -> None:
        super().__init__(message)
        self.path = path
        self.message = message


def _format_yaml_error(path: Path, exc: yaml.YAMLError) -> str:
    if exc.problem_mark is not None:
        line_number = exc.problem_mark.line + 1
        column_number = exc.problem_mark.column + 1
        problem = exc.problem or str(exc)
        return f"Invalid YAML in {path} at line {line_number}, column {column_number}: {problem}"
    return f"Invalid YAML in {path}: {exc}"


def _format_validation_error(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "<root>"
        details.append(f"{location}: {error.get('msg', 'Invalid value.')}")
    return "; ".join(details)


def _format_prefixed_validation_error(prefix: str, exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors():
        suffix = ".".join(str(part) for part in error.get("loc", ()))
        location = f"{prefix}.{suffix}" if suffix else prefix
        details.append(f"{location}: {error.get('msg', 'Invalid value.')}")
    return "; ".join(details)


def _validation_errors_are_only_missing_required_fields(exc: ValidationError) -> bool:
    return all(error.get("type") == "missing" for error in exc.errors())


def _can_be_incomplete_template_profile(
    profile_name: str,
    raw_profile: dict,
    referenced_base_profiles: set[str],
) -> bool:
    return profile_name in referenced_base_profiles or bool(raw_profile.get("base"))


def _load_yaml_file(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return yaml.safe_load(stream) or {}
    except FileNotFoundError as exc:
        raise ConfigLoadError(path, f"Config file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigLoadError(path, _format_yaml_error(path, exc)) from exc


def _resolve_env_references(value):
    if isinstance(value, dict):
        return {key: _resolve_env_references(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_env_references(item) for item in value]
    if isinstance(value, str):
        match = ENV_REFERENCE_PATTERN.fullmatch(value)
        if match is None:
            return value
        env_value = os.environ.get(match.group(1))
        return env_value if env_value not in (None, "") else None
    return value


def _resolve_translator_profile_bases(path: Path, data: dict) -> None:
    llm_data = data.get("llm")
    if not isinstance(llm_data, dict):
        return

    translator_data = llm_data.get("translator")
    if not isinstance(translator_data, dict):
        return

    referenced_base_profiles: set[str] = set()
    for raw_profile in translator_data.values():
        if not isinstance(raw_profile, dict):
            continue
        raw_bases = raw_profile.get("base", [])
        if isinstance(raw_bases, list):
            referenced_base_profiles.update(
                base_name for base_name in raw_bases if isinstance(base_name, str)
            )

    resolved_profiles: dict[str, dict] = {}
    resolution_stack: list[str] = []

    def resolve_profile(profile_name: str) -> dict:
        if profile_name in resolved_profiles:
            return resolved_profiles[profile_name]

        if profile_name in resolution_stack:
            cycle = " -> ".join([*resolution_stack, profile_name])
            raise ConfigLoadError(
                path,
                f"Translator profile inheritance cycle in {path}: {cycle}",
            )

        raw_profile = translator_data.get(profile_name)
        if not isinstance(raw_profile, dict):
            raise ConfigLoadError(
                path,
                f"Invalid configuration in {path}: llm.translator.{profile_name} must be a mapping.",
            )

        raw_bases = raw_profile.get("base", [])
        if not isinstance(raw_bases, list):
            raise ConfigLoadError(
                path,
                f"Invalid configuration in {path}: llm.translator.{profile_name}.base must be a list of profile names.",
            )
        for index, base_name in enumerate(raw_bases):
            if isinstance(base_name, str):
                continue
            if base_name is None:
                raise ConfigLoadError(
                    path,
                    "Invalid configuration in "
                    f"{path}: llm.translator.{profile_name}.base.{index} must resolve to a profile name.",
                )
            raise ConfigLoadError(
                path,
                f"Invalid configuration in {path}: llm.translator.{profile_name}.base must be a list of profile names.",
            )

        resolution_stack.append(profile_name)
        try:
            merged_profile: dict = {}
            for base_name in raw_bases:
                if base_name not in translator_data:
                    raise ConfigLoadError(
                        path,
                        "Invalid configuration in "
                        f"{path}: llm.translator.{profile_name} references unknown base profile '{base_name}'.",
                    )
                merged_profile.update(resolve_profile(base_name))

            for field_name, field_value in raw_profile.items():
                if field_name == "base":
                    continue
                merged_profile[field_name] = field_value
        finally:
            resolution_stack.pop()

        resolved_profiles[profile_name] = merged_profile
        return merged_profile

    resolved_translator_data: dict[str, dict] = {}
    for profile_name in list(translator_data):
        resolved_profile = resolve_profile(profile_name)
        raw_profile = translator_data.get(profile_name)
        try:
            TranslatorProfileConfig.model_validate(resolved_profile)
        except ValidationError as exc:
            if (
                isinstance(raw_profile, dict)
                and _validation_errors_are_only_missing_required_fields(exc)
                and _can_be_incomplete_template_profile(
                    profile_name,
                    raw_profile,
                    referenced_base_profiles,
                )
            ):
                continue
            raise ConfigLoadError(
                path,
                "Invalid configuration in "
                f"{path}: {_format_prefixed_validation_error(f'llm.translator.{profile_name}', exc)}",
            ) from exc
        resolved_translator_data[profile_name] = resolved_profile

    translator_data.clear()
    translator_data.update(resolved_translator_data)


def load_workspace_config(path: Path) -> WorkspaceConfig:
    data = _resolve_env_references(_load_yaml_file(path))
    _resolve_translator_profile_bases(path, data)
    try:
        return WorkspaceConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigLoadError(path, f"Invalid configuration in {path}: {_format_validation_error(exc)}") from exc


def load_local_workflow_config(path: Path) -> LocalWorkflowConfig:
    data = _resolve_env_references(_load_yaml_file(path))
    try:
        return LocalWorkflowConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigLoadError(path, f"Invalid configuration in {path}: {_format_validation_error(exc)}") from exc