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

    if hasattr(channels_config, "teams") and channels_config.teams.enabled:
        from hermclaw.body.channels.teams import TeamsAdapter

        webhook_url = secrets_resolver(channels_config.teams.webhook_url_env)
        if webhook_url:
            adapters["teams"] = TeamsAdapter(webhook_url=webhook_url)

    if hasattr(channels_config, "signal") and channels_config.signal.enabled:
        from hermclaw.body.channels.signal import SignalAdapter

        api_url = secrets_resolver(channels_config.signal.api_url_env) or "http://localhost:8080"
        number = secrets_resolver(channels_config.signal.number_env) or ""
        adapters["signal"] = SignalAdapter(api_url=api_url, phone=number)

    if hasattr(channels_config, "matrix") and channels_config.matrix.enabled:
        from hermclaw.body.channels.messaging_extras import MatrixAdapter

        homeserver = secrets_resolver(channels_config.matrix.homeserver_env) or "https://matrix.org"
        token = secrets_resolver(channels_config.matrix.access_token_env) or ""
        room_id = secrets_resolver(channels_config.matrix.room_id_env) or ""
        adapters["matrix"] = MatrixAdapter(homeserver=homeserver, access_token=token, room_id=room_id)

    if hasattr(channels_config, "google_chat") and channels_config.google_chat.enabled:
        from hermclaw.body.channels.messaging_extras import GoogleChatAdapter

        webhook_url = secrets_resolver(channels_config.google_chat.webhook_url_env)
        if webhook_url:
            adapters["google_chat"] = GoogleChatAdapter(webhook_url=webhook_url)

    if hasattr(channels_config, "feishu") and channels_config.feishu.enabled:
        from hermclaw.body.channels.messaging_extras import FeishuLarkAdapter

        webhook_url = secrets_resolver(channels_config.feishu.webhook_url_env)
        if webhook_url:
            adapters["feishu"] = FeishuLarkAdapter(webhook_url=webhook_url)

    if hasattr(channels_config, "mattermost") and channels_config.mattermost.enabled:
        from hermclaw.body.channels.messaging_extras import MattermostAdapter

        server_url = secrets_resolver(channels_config.mattermost.server_url_env) or ""
        token = secrets_resolver(channels_config.mattermost.token_env) or ""
        adapters["mattermost"] = MattermostAdapter(server_url=server_url, token=token)

    if hasattr(channels_config, "twilio") and channels_config.twilio.enabled:
        from hermclaw.body.channels.messaging_extras import TwilioSMSAdapter

        sid = secrets_resolver(channels_config.twilio.account_sid_env) or ""
        token = secrets_resolver(channels_config.twilio.auth_token_env) or ""
        from_num = secrets_resolver(channels_config.twilio.from_number_env) or ""
        adapters["twilio"] = TwilioSMSAdapter(account_sid=sid, auth_token=token, from_number=from_num)

    if hasattr(channels_config, "webhook") and channels_config.webhook.enabled:
        from hermclaw.body.channels.messaging_extras import GenericWebhookAdapter

        webhook_url = secrets_resolver(channels_config.webhook.webhook_url_env) or ""
        secret = secrets_resolver(channels_config.webhook.secret_env) or ""
        adapters["webhook"] = GenericWebhookAdapter(webhook_url=webhook_url, secret=secret)

    return adapters
