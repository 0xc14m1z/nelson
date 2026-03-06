from dataclasses import dataclass

import httpx


@dataclass
class ValidationConfig:
    url: str
    headers: dict[str, str]


def get_validation_config(provider_slug: str, base_url: str) -> ValidationConfig:
    if provider_slug == "anthropic":
        return ValidationConfig(
            url=f"{base_url}/v1/models",
            headers={"x-api-key": "{key}", "anthropic-version": "2023-06-01"},
        )
    if provider_slug == "google":
        return ValidationConfig(
            url=f"{base_url}/models?key={{key}}",
            headers={},
        )
    # OpenAI, Mistral, OpenRouter, and any future provider
    return ValidationConfig(
        url=f"{base_url}/models",
        headers={"Authorization": "Bearer {key}"},
    )


async def validate_api_key(provider_slug: str, base_url: str, raw_key: str) -> tuple[bool, str | None]:
    config = get_validation_config(provider_slug, base_url)
    url = config.url.replace("{key}", raw_key)
    headers = {k: v.replace("{key}", raw_key) for k, v in config.headers.items()}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code in (200, 201):
                return True, None
            if resp.status_code in (401, 403):
                return False, "Invalid API key"
            return False, f"Unexpected status {resp.status_code}"
    except httpx.TimeoutException:
        return False, "Validation request timed out"
    except httpx.RequestError as e:
        return False, f"Connection error: {e}"
