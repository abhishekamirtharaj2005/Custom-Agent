"""ASCII art banner and branding system for Hermclaw."""

HERMCLAW_BANNER = r"""
  _    _                      ____ _
 | |  | |                    / ___| |
 | |__| | ___ _ __ _ __ ___ | |   | | __ ___      __
 |  __  |/ _ \ '__| '_ ` _ \| |   | |/ _` \ \ /\ / /
 | |  | |  __/ |  | | | | | | |___| | (_| |\ V  V /
 |_|  |_|\___|_|  |_| |_| |_|\____|_|\__,_| \_/\_/

     A Unified, Self-Improving Personal AI Agent
"""

HERMCLAW_BANNER_SMALL = r"""
 ╦ ╦┌─┐┬─┐┌┬┐╔═╗┬  ┌─┐┬ ┬
 ╠═╣├┤ ├┬┘│││║  │  ├─┤│││
 ╩ ╩└─┘┴└─┴ ┴╚═╝┴─┘┴ ┴└┴┘
"""

HERMCLAW_BANNER_MINIMAL = "--- HermClaw v0.1.0 ---"

HERMCLAW_CRAB = r"""
    .----.
   / o  o \
  (  >  <  )
   \  --  /
  /|      |\
 / |  /\  | \
(__|_/  \_|__)
"""

VERSION = "0.1.0"
CODENAME = "Hermit"

STARTUP_MESSAGE = f"""{HERMCLAW_BANNER}
  Version {VERSION} ({CODENAME})
  Type /help for commands, /exit to quit.
"""


def get_banner(style: str = "full") -> str:
    """Get the banner in the specified style."""
    if style == "small":
        return HERMCLAW_BANNER_SMALL
    elif style == "minimal":
        return HERMCLAW_BANNER_MINIMAL
    elif style == "crab":
        return HERMCLAW_CRAB
    return HERMCLAW_BANNER


def get_startup_message() -> str:
    return STARTUP_MESSAGE
