"""Invented after-action process death; importable without the history fixture graph."""

import os
from dataclasses import dataclass, replace

from olist_support.routing_provider import RoutingProviderFactory


@dataclass(frozen=True)
class CrashAfterActionAgent:
    agent: object

    def run(self, context, value, gateway):
        self.agent.run(context, value, gateway)
        os._exit(37)


@dataclass(frozen=True)
class CrashAfterActionFactory(RoutingProviderFactory):
    def build(self, context, state):
        parts = super().build(context, state)
        return replace(parts, agent=CrashAfterActionAgent(parts.agent))
