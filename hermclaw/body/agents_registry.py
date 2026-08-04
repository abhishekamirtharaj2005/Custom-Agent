"""Multi-agent identity routing: resolves which identity (name/emoji) and
which profile an incoming message should be handled under.

agent.list lets one Hermclaw installation present as several identities
(e.g. a general assistant and a dedicated support bot), each bound to
its own profile so their memory, skills, and identity files never mix.
With an empty list (the common case), everything resolves to a single
default identity built from agent.name / agent.default_profile.
"""

from __future__ import annotations

import dataclasses
from typing import Optional


@dataclasses.dataclass(frozen=True)
class ResolvedAgent:
    id: str
    name: str
    emoji: Optional[str]
    profile: str


class AgentsRegistry:
    def __init__(self, agent_config) -> None:  # config.AgentConfig; loosely typed to avoid an import cycle
        self._by_id: dict[str, ResolvedAgent] = {}
        self._default: ResolvedAgent

        if agent_config.entries:
            for entry in agent_config.entries:
                self._by_id[entry.id] = ResolvedAgent(
                    id=entry.id, name=entry.identity.name, emoji=entry.identity.emoji, profile=entry.profile,
                )
            self._default = next(iter(self._by_id.values()))
        else:
            self._default = ResolvedAgent(
                id="default", name=agent_config.name, emoji=None, profile=agent_config.default_profile,
            )
            self._by_id["default"] = self._default

    def resolve(self, agent_id: Optional[str] = None) -> ResolvedAgent:
        if agent_id and agent_id in self._by_id:
            return self._by_id[agent_id]
        return self._default

    def resolve_for_message(self, channel: str, account: Optional[str] = None) -> ResolvedAgent:
        """`account` is the channel-supplied hint (e.g. which bot token
        or account received the message) used by IncomingMessage.account.
        Falls back to the default identity when there's no match or no
        hint -- the common single-identity case."""
        if account:
            return self.resolve(account)
        return self._default

    def all_agents(self) -> list[ResolvedAgent]:
        return list(self._by_id.values())

    def profiles_in_use(self) -> list[str]:
        return sorted({a.profile for a in self._by_id.values()})
