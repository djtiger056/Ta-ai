import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.providers.openai_provider import OpenAIProvider


def test_top_level_llm_fields_override_provider_defaults():
    provider = OpenAIProvider(
        "yunwu",
        llm_config={
            "provider": "yunwu",
            "api_base": "https://user.example/v1",
            "api_key": "user-key",
            "model": "user-model",
            "temperature": 0.4,
            "max_tokens": 321,
            "yunwu": {
                "api_base": "https://old.example/v1",
                "api_key": "old-key",
                "model": "old-model",
                "temperature": 0.9,
                "max_tokens": 999,
            },
        },
    )

    assert provider.api_base == "https://user.example/v1"
    assert provider.api_key == "user-key"
    assert provider.model == "user-model"
    assert provider.temperature == 0.4
    assert provider.max_tokens == 321


def test_provider_nested_config_is_fallback_when_top_level_empty():
    provider = OpenAIProvider(
        "qwen",
        llm_config={
            "provider": "qwen",
            "qwen": {
                "api_base": "https://dashscope.example/v1",
                "api_key": "nested-key",
                "model": "nested-model",
            },
        },
    )

    assert provider.api_base == "https://dashscope.example/v1"
    assert provider.api_key == "nested-key"
    assert provider.model == "nested-model"
