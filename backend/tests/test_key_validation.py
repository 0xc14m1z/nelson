from app.keys.validation import get_validation_config


def test_openai_validation_config():
    config = get_validation_config("openai", "https://api.openai.com/v1")
    assert config.url == "https://api.openai.com/v1/models"
    assert config.headers["Authorization"] == "Bearer {key}"


def test_anthropic_validation_config():
    config = get_validation_config("anthropic", "https://api.anthropic.com")
    assert config.url == "https://api.anthropic.com/v1/models"
    assert config.headers["x-api-key"] == "{key}"
    assert "anthropic-version" in config.headers


def test_google_validation_config():
    config = get_validation_config("google", "https://generativelanguage.googleapis.com/v1beta")
    assert "key={key}" in config.url


def test_unknown_provider_uses_bearer():
    config = get_validation_config("some-new-provider", "https://api.example.com/v1")
    assert config.url == "https://api.example.com/v1/models"
    assert config.headers["Authorization"] == "Bearer {key}"
