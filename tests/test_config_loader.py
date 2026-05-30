from pathlib import Path

from do_my_work.infrastructure.config_loader import load_workspace_config


def test_load_workspace_config_reads_translator_profiles(tmp_path: Path) -> None:
    config_file = tmp_path / "workspace.yaml"
    config_file.write_text(
        """
input_dir: inbound
output_dir: outbound
data_dir: state
llm:
  translator:
    technical:
      url: http://mock.example:11434
      model: mock-llama
      timeout_seconds: 240
      max_retries: 2
      max_pre_context_bytes: 120
      max_post_context_bytes: 240
      temperature: 0.1
      system_prompt: You are a technical translator.
      user_prompt: |
        ===BEGIN SOURCE TEXT===
        ${input_fragment}
        ===END SOURCE TEXT===
    emotional:
      url: http://cloud.example:11434
      model: mock-emotional
      credential: secret-token
      temperature: 0.7
      system_prompt: You are an emotional translator.
      user_prompt: "Translate this fragment: ${input_fragment}"
""".strip(),
        encoding="utf-8",
    )

    config = load_workspace_config(config_file)

    assert config.input_dir == Path("inbound")
    assert config.llm.translator["technical"].url == "http://mock.example:11434"
    assert config.llm.translator["technical"].timeout_seconds == 240
    assert config.llm.translator["technical"].max_retries == 2
    assert config.llm.translator["technical"].max_pre_context_bytes == 120
    assert config.llm.translator["technical"].max_post_context_bytes == 240
    assert config.llm.translator["technical"].temperature == 0.1
    assert config.llm.translator["emotional"].credential == "secret-token"
    assert "${input_fragment}" in config.llm.translator["emotional"].user_prompt