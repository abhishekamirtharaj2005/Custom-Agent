"""Transport factory: turns a validated ModelConfig into a live
ProviderTransport, resolving its *_env secret references at the point of
use (never eagerly, never persisted) -- see hermclaw/security/secrets.py.
"""

from __future__ import annotations

from hermclaw.brain.transports.base import ProviderTransport, TransportError
from hermclaw.security.secrets import resolve_env_ref

__all__ = ["ProviderTransport", "TransportError", "build_transport", "MissingCredentialsError"]


class MissingCredentialsError(Exception):
    """Raised with an actionable message, never a bare stack trace --
    surfaced by the CLI as a clean error (see C.2.9's acceptance)."""


def build_transport(model_config) -> ProviderTransport:  # ModelConfig, kept untyped to avoid a config.py<->transports import cycle
    provider = model_config.provider

    if provider == "anthropic":
        api_key = resolve_env_ref(model_config.api_key_env)
        if not api_key:
            raise MissingCredentialsError(
                f"No API key found for provider 'anthropic'. "
                f"Set the {model_config.api_key_env} environment variable "
                f"(see brain.model.api_key_env in your config)."
            )
        from hermclaw.brain.transports.anthropic import AnthropicTransport

        api_base = resolve_env_ref(model_config.api_base_env) if model_config.api_base_env else None
        return AnthropicTransport(api_key=api_key, model_name=model_config.model_name, api_base=api_base)

    if provider == "openai_compat":
        api_key = resolve_env_ref(model_config.api_key_env)
        api_base = resolve_env_ref(model_config.api_base_env) if model_config.api_base_env else None
        if not api_base:
            raise MissingCredentialsError(
                f"provider 'openai_compat' requires an api_base -- "
                f"set brain.model.api_base_env to an environment variable holding the server URL."
            )
        from hermclaw.brain.transports.openai_compat import ChatCompletionsTransport

        return ChatCompletionsTransport(api_key=api_key, model_name=model_config.model_name, api_base=api_base)

    if provider == "bedrock":
        try:
            from hermclaw.brain.transports.bedrock import BedrockTransport
        except ImportError as exc:
            raise MissingCredentialsError(
                "provider 'bedrock' requires the optional 'bedrock' extra: pip install 'hermclaw[bedrock]'"
            ) from exc
        return BedrockTransport(model_name=model_config.model_name)

    raise TransportError(f"Unknown provider: {provider!r}")
