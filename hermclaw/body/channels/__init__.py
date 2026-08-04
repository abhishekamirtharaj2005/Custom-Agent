"""Channel adapters: cli, web, telegram, discord, slack, whatsapp -- all
implementing the same ChannelAdapter ABC (base.py) so the gateway and
scheduler never need channel-specific branches.
"""

from __future__ import annotations

from hermclaw.body.channels.base import ChannelAdapter, ChannelHealth, IncomingMessage, OutgoingMessage

__all__ = ["ChannelAdapter", "ChannelHealth", "IncomingMessage", "OutgoingMessage", "build_enabled_channels"]


def build_enabled_channels(channels_config, secrets_resolver) -> dict[str, ChannelAdapter]:
    """Constructs one adapter per enabled channel in config, resolving
    each *_env token/secret reference at construction time. `channels_config`
    is a config.ChannelsConfig; kept loosely typed here to avoid a config.py
    <-> body import cycle."""
    adapters: dict[str, ChannelAdapter] = {}

    if channels_config.cli.enabled:
        from hermclaw.body.channels.cli_channel import CliChannel

        adapters["cli"] = CliChannel()

    if channels_config.web.enabled:
        from hermclaw.body.channels.web import WebChannel

        adapters["web"] = WebChannel()

    if channels_config.telegram.enabled:
        from hermclaw.body.channels.telegram import TelegramChannel

        token = secrets_resolver(channels_config.telegram.bot_token_env)
        if token:
            adapters["telegram"] = TelegramChannel(bot_token=token, mode=channels_config.telegram.mode)

    if channels_config.discord.enabled:
        from hermclaw.body.channels.discord import DiscordChannel

        token = secrets_resolver(channels_config.discord.bot_token_env)
        if token:
            adapters["discord"] = DiscordChannel(bot_token=token)

    if channels_config.slack.enabled:
        from hermclaw.body.channels.slack import SlackChannel

        bot_token = secrets_resolver(channels_config.slack.bot_token_env)
        app_token = secrets_resolver(channels_config.slack.app_token_env)
        if bot_token and app_token:
            adapters["slack"] = SlackChannel(bot_token=bot_token, app_token=app_token)

    if channels_config.whatsapp.enabled:
        from hermclaw.body.channels.whatsapp import WhatsAppChannel

        cmd = channels_config.whatsapp.sidecar_command.split() if channels_config.whatsapp.sidecar_command else None
        adapters["whatsapp"] = WhatsAppChannel(sidecar_command=cmd)

    return adapters
