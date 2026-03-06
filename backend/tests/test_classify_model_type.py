import pytest

from app.openrouter.service import _classify_model_type

# Realistic supported_parameters from OpenRouter API
REASONING_ONLY_PARAMS = ["include_reasoning", "max_tokens", "reasoning", "response_format", "seed"]
HYBRID_PARAMS = ["frequency_penalty", "include_reasoning", "reasoning", "temperature", "max_tokens"]
CHAT_PARAMS = ["frequency_penalty", "max_tokens", "temperature", "top_p", "stop"]


@pytest.mark.parametrize(
    "slug, name, params, expected",
    [
        # Pure reasoning (has reasoning, no temperature) — like o3, o4-mini
        ("openai/o3", "o3", REASONING_ONLY_PARAMS, "reasoning"),
        ("openai/o4-mini", "o4 Mini", REASONING_ONLY_PARAMS, "reasoning"),
        # Hybrid (has reasoning + temperature) — like GPT-5.4, Claude, Gemini
        ("openai/gpt-5.4-pro", "GPT-5.4 Pro", HYBRID_PARAMS, "hybrid"),
        ("anthropic/claude-sonnet-4.6", "Claude Sonnet 4.6", HYBRID_PARAMS, "hybrid"),
        ("google/gemini-2.5-pro", "Gemini 2.5 Pro", HYBRID_PARAMS, "hybrid"),
        ("deepseek/deepseek-r1", "DeepSeek R1", HYBRID_PARAMS, "hybrid"),
        ("deepseek/deepseek-v3.2", "DeepSeek V3.2", HYBRID_PARAMS, "hybrid"),
        # Chat (no reasoning param)
        ("mistralai/mistral-large", "Mistral Large", CHAT_PARAMS, "chat"),
        ("meta-llama/llama-3.1-70b", "Llama 3.1 70B", CHAT_PARAMS, "chat"),
        # Code models (name-based override)
        ("qwen/qwen3-coder", "Qwen3 Coder", CHAT_PARAMS, "code"),
        ("mistralai/codestral-latest", "Codestral", CHAT_PARAMS, "code"),
        # Diffusion models (name-based override)
        ("inception/mercury-coder-small", "Mercury Coder Small", CHAT_PARAMS, "diffusion"),
        # No params at all
        ("unknown/model", "Unknown Model", None, None),
        ("unknown/model", "Unknown Model", [], None),
    ],
)
def test_classify_model_type(slug, name, params, expected):
    assert _classify_model_type(slug, name, params) == expected
