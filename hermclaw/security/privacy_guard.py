"""Privacy & Safety Sandbox: sensitive window masking and action risk policies.

Protects user privacy by:
1. Detecting sensitive on-screen applications (passwords, banking, 2FA, crypto, incognito).
2. Blurring / masking sensitive regions in visual screenshots before LLM transmission.
3. Classifying and gating high-risk tool operations via configurable security policies.
"""

from __future__ import annotations

import re
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

# Default keywords indicating sensitive windows that must not be exposed to models
SENSITIVE_WINDOW_KEYWORDS: list[str] = [
    # Passwords & Credential Managers
    "1password", "bitwarden", "lastpass", "keepass", "dashlane", "keychain", "authenticator",
    "2fa", "otp", "totp", "yubikey", "credentials",
    # Financial & Banking
    "bank", "banking", "chase", "wells fargo", "citibank", "paypal", "stripe", "venmo",
    "revolut", "credit card", "debit card", "account balance",
    # Crypto & Web3
    "metamask", "phantom", "coinbase", "binance", "kraken", "ledger live", "seed phrase", "private key",
    # Private Browsing & Secrets
    "incognito", "inprivate", "private browsing", ".env", "id_rsa", "id_ed25519",
]

# Sensitive text patterns (e.g. credit cards, API keys)
SENSITIVE_REGEX_PATTERNS = [
    re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b"),  # CC
    re.compile(r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AIza[0-9A-Za-z-_]{35})\b"),  # API tokens
]


class PrivacyGuard:
    """Detects sensitive content and masks screenshots or sensitive window regions."""

    def __init__(self, sensitive_keywords: Optional[list[str]] = None) -> None:
        self.sensitive_keywords = [
            k.lower() for k in (sensitive_keywords or SENSITIVE_WINDOW_KEYWORDS)
        ]

    def is_window_sensitive(self, title: str) -> bool:
        """Return True if window title suggests sensitive/private information."""
        if not title:
            return False
        title_lower = title.lower()
        return any(k in title_lower for k in self.sensitive_keywords)

    def mask_screenshot_if_sensitive(
        self,
        image: Any,
        active_window_title: str,
        window_bounds: Optional[tuple[int, int, int, int]] = None,
    ) -> tuple[Any, bool]:
        """If the active or target window is sensitive, blur or mask that region."""
        if not self.is_window_sensitive(active_window_title):
            return image, False

        try:
            from PIL import ImageDraw, ImageFilter

            # If specific bounds provided, mask that rectangle
            if window_bounds and len(window_bounds) == 4:
                x, y, w, h = window_bounds
                draw = ImageDraw.Draw(image)
                draw.rectangle([x, y, x + w, y + h], fill=(30, 30, 30), outline=(255, 0, 0), width=3)
                draw.text((x + 20, y + 20), "🔒 [Hermclaw Privacy Guard: Sensitive Content Masked]", fill=(255, 255, 255))
            else:
                # Mask entire image with a heavy blur and privacy banner
                blurred = image.filter(ImageFilter.GaussianBlur(radius=25))
                draw = ImageDraw.Draw(blurred)
                w, h = image.size
                banner_box = [w // 6, h // 3, 5 * w // 6, 2 * h // 3]
                draw.rectangle(banner_box, fill=(20, 20, 20, 220), outline=(220, 50, 50), width=4)
                draw.text(
                    (w // 6 + 40, h // 2 - 20),
                    f"🔒 [Hermclaw Privacy Shield Active]\nDetected Sensitive Window: {active_window_title[:40]}\nVisual content hidden to prevent credential leakage.",
                    fill=(255, 255, 255),
                )
                image = blurred

            logger.info("privacy_guard.masked_screenshot", window=active_window_title)
            return image, True
        except Exception as exc:
            logger.warning("privacy_guard.mask_failed", error=str(exc))
            return image, False


class ActionRiskPolicy:
    """Classifies tool actions by risk level and enforces execution gates."""

    RISK_SAFE = "safe"
    RISK_MODERATE = "moderate"
    RISK_CRITICAL = "critical"

    POLICY_STRICT = "strict"        # Ask confirmation for moderate and critical
    POLICY_BALANCED = "balanced"    # Ask confirmation for critical only
    POLICY_PERMISSIVE = "permissive"# Allow all without confirmation

    def __init__(self, mode: str = POLICY_BALANCED) -> None:
        self.mode = mode

    def classify_action(self, tool_name: str, args: dict[str, Any]) -> str:
        """Classify tool action risk level."""
        # Critical risks: destructive operations
        if tool_name == "shell":
            cmd = str(args.get("command", "")).lower()
            if any(p in cmd for p in ["rm -rf", "format", "del /f", "drop database", "mkfs", "dd if="]):
                return self.RISK_CRITICAL
            return self.RISK_MODERATE

        if tool_name == "git":
            action = str(args.get("action", "")).lower()
            if action in ["push", "reset", "clean"] and "--force" in str(args):
                return self.RISK_CRITICAL
            return self.RISK_MODERATE

        if tool_name == "code_exec":
            return self.RISK_MODERATE

        if tool_name == "file_edit" or tool_name == "file_write":
            path = str(args.get("path", "")).lower()
            if any(s in path for s in ["system32", "/etc/", ".ssh", "id_rsa"]):
                return self.RISK_CRITICAL
            return self.RISK_MODERATE

        if tool_name in ["computer", "screen_vision"]:
            action = str(args.get("action", "")).lower()
            if action in ["click", "type", "paste", "key", "hotkey", "click_element"]:
                return self.RISK_MODERATE
            return self.RISK_SAFE

        return self.RISK_SAFE

    def is_approval_required(self, tool_name: str, args: dict[str, Any]) -> tuple[bool, str]:
        """Check if action requires explicit user approval under current policy."""
        risk = self.classify_action(tool_name, args)

        if self.mode == self.POLICY_PERMISSIVE:
            return False, risk
        elif self.mode == self.POLICY_BALANCED:
            return (risk == self.RISK_CRITICAL), risk
        elif self.mode == self.POLICY_STRICT:
            return (risk in [self.RISK_MODERATE, self.RISK_CRITICAL]), risk

        return False, risk


# Global default instances
default_privacy_guard = PrivacyGuard()
default_risk_policy = ActionRiskPolicy()
