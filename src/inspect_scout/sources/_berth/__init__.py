"""Berth source for Inspect Scout.

Reads agent sessions through the Berth CLI (`berth project <p> session ls|show`),
so every agent Berth declares a `sessions.json` for (Claude Code, Codex, Pi, ...)
imports the same way. Berth owns session parsing; this module only maps its
OpenAI-format messages to Scout transcripts.
"""

from .transcripts import BERTH_SOURCE_TYPE, berth

__all__ = ["berth", "BERTH_SOURCE_TYPE"]
