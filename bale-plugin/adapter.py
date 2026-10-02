"""Bale adapter — a thin subclass of the Telegram adapter.

Bale's Bot API (docs.bale.ai) is Telegram's Bot API with minor changes, so we
reuse Hermes' full Telegram adapter and override only what differs:

  * API base URL  -> https://tapi.bale.ai/bot   (set via PlatformConfig.extra.base_url)
  * Bot token     -> BALE_BOT_TOKEN             (instead of TELEGRAM_BOT_TOKEN)
  * Allowed users -> BALE_ALLOWED_USERS         (falls back to TELEGRAM_ALLOWED_USERS)

All slash commands, the command list, session binding, inline keyboards, media,
voice, and delivery behavior are inherited unchanged from TelegramAdapter — the
Bale experience is therefore exactly the Telegram experience.

NOTE on the base URL: python-telegram-bot builds the final endpoint as
``base_url + token`` (NOT ``base_url + "bot" + token``), so the Bale base URL
MUST end in ``/bot`` — i.e. ``https://tapi.bale.ai/bot``. That yields
``https://tapi.bale.ai/bot<token>`` which is exactly what Bale's Bot API expects
(the documented endpoint is ``https://tapi.bale.ai/bot<token>/getMe``).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Re-use the real Telegram adapter implementation.
from plugins.platforms.telegram.adapter import (  # noqa: E402
    TelegramAdapter,
    check_telegram_requirements,
    Platform,
    PlatformConfig,
)
from gateway.platform_registry import (  # noqa: E402
    PlatformEntry,
    platform_registry,
)

# IMPORTANT: PTB concatenates base_url + token, so this MUST end in "/bot".
_BALE_API_BASE = "https://tapi.bale.ai/bot"
_BALE_TOKEN_ENV = "BALE_BOT_TOKEN"
_BALE_ALLOWED_ENV = "BALE_ALLOWED_USERS"
_BALE_CHAT_ID_ENV = "BALE_CHAT_ID"


def _bale_token() -> str:
    return os.getenv(_BALE_TOKEN_ENV, "").strip()


def _bale_allowed_users() -> str:
    allowed = os.getenv(_BALE_ALLOWED_ENV, "").strip()
    chat_id = os.getenv(_BALE_CHAT_ID_ENV, "").strip()
    parts = [p for p in allowed.split(",") if p.strip()]
    if chat_id and chat_id not in parts:
        parts.append(chat_id)
    return ",".join(parts)


class BaleAdapter(TelegramAdapter):
    """Drop-in Bale adapter: same engine as Telegram, different endpoint/token."""

    # Bale message limit matches Telegram's 4096-char cap.
    MAX_MESSAGE_LENGTH = 4096

    def __init__(self, config: PlatformConfig):
        # Inject the Bale token + base_url BEFORE TelegramAdapter.__init__ reads
        # config.token / config.extra.  We mutate the passed config object in
        # place so the parent's connect() (which reads self.config.token and
        # extra["base_url"]) sees Bale values.
        if not getattr(config, "token", None):
            config.token = _bale_token()
        extra = dict(getattr(config, "extra", {}) or {})
        # Force the Bale endpoint. PTB appends the token to base_url, so the
        # value must end in "/bot".
        extra["base_url"] = _BALE_API_BASE
        extra["base_file_url"] = _BALE_API_BASE
        try:
            config.extra = extra
        except AttributeError:
            # PlatformConfig may use a different setter; fall back to __dict__.
            config.__dict__["extra"] = extra
        super().__init__(config)
        # Tell the engine this is Bale (some logs / delivery keys rely on platform).
        try:
            self.platform = Platform("bale")
        except Exception:
            pass

    def _bale_auth_env(self) -> set[str]:
        values = set()
        if os.getenv("BALE_ALLOW_ALL_USERS", "").strip().lower() in {"1", "true", "yes", "on"}:
            values.add("*")
        values.update(part.strip() for part in _bale_allowed_users().split(",") if part.strip())
        return values

    def _is_user_authorized_from_message(self, message) -> bool:  # type: ignore[override]
        source = self._source_from_message_for_auth(message)
        user_id = source.user_id
        if not user_id:
            return True
        allowed = self._bale_auth_env()
        if "*" in allowed or user_id in allowed:
            return True
        return self._should_pass_unauthorized_dm_for_pairing(source)

    def _should_pass_unauthorized_dm_for_pairing(self, source) -> bool:  # type: ignore[override]
        if source.chat_type != "dm":
            return False
        runner = getattr(getattr(self, "_message_handler", None), "__self__", None)
        behavior_fn = getattr(runner, "_get_unauthorized_dm_behavior", None)
        if callable(behavior_fn):
            try:
                return behavior_fn(
                    Platform("bale"), profile=getattr(source, "profile", None)
                ) == "pair"
            except Exception:
                logger.debug("[Bale] Failed to resolve unauthorized DM behavior", exc_info=True)
        extra = getattr(getattr(self, "config", None), "extra", None) or {}
        return str(extra.get("unauthorized_dm_behavior", "")).strip().lower() == "pair"

    def _telegram_fallback_transport_allowed(self) -> bool:  # type: ignore[override]
        return False

    def _fallback_ips(self):  # type: ignore[override]
        return []



def _build_adapter(config):
    adapter = BaleAdapter(config)
    try:
        adapter._notifications_mode = _resolve_notifications_mode()
    except Exception:
        adapter._notifications_mode = "important"
    return adapter


def _resolve_notifications_mode() -> str:
    try:
        import hermes_cli.gateway as gateway_mod
        return getattr(gateway_mod, "get_notifications_mode", lambda: "important")()
    except Exception:
        return "important"


def _is_connected(config) -> bool:
    token = getattr(config, "token", None)
    if not token:
        token = _bale_token()
    return bool(str(token).strip())


def _apply_yaml_config(yaml_cfg: dict, bale_cfg: dict) -> dict | None:
    """Inject Bale-specific extras (base_url) into PlatformConfig.extra.

    Mirrors the telegram apply_yaml_config_fn contract: called from
    load_gateway_config() BEFORE the adapter is constructed, so the adapter
    sees base_url in config.extra.
    """
    extras: dict = {}
    extras["base_url"] = _BALE_API_BASE
    extras["base_file_url"] = _BALE_API_BASE
    tok = _bale_token()
    if tok:
        extras["_bale_token"] = tok
    allowed = _bale_allowed_users()
    if allowed:
        extras["_bale_allowed"] = allowed
    return extras or None


def register(ctx) -> None:
    """Plugin entry point — called by the Hermes plugin system."""
    ctx.register_platform(
        name="bale",
        label="Bale",
        adapter_factory=_build_adapter,
        check_fn=check_telegram_requirements,
        is_connected=_is_connected,
        required_env=[_BALE_TOKEN_ENV],
        install_hint="Set BALE_BOT_TOKEN in ~/.hermes/.env (and BALE_ALLOWED_USERS).",
        allowed_users_env=_BALE_ALLOWED_ENV,
        allow_all_env="BALE_ALLOW_ALL_USERS",
        cron_deliver_env_var="BALE_HOME_CHANNEL",
        max_message_length=4096,
        emoji="📦",
        allow_update_command=True,
        plugin_name="bale-platform",
        apply_yaml_config_fn=_apply_yaml_config,
    )
