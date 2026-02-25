"""Tests for MCP tool caching in EvoScientist.EvoScientist."""

from __future__ import annotations

import EvoScientist.EvoScientist as agent_module


def _reset_mcp_cache() -> None:
    agent_module._MCP_TOOLS_CACHE_KEY = None
    agent_module._MCP_TOOLS_CACHE_VALUE = None


class TestMcpToolCaching:
    def setup_method(self) -> None:
        _reset_mcp_cache()

    def test_reuses_cached_tools_when_config_unchanged(self, monkeypatch):
        calls = {"load": 0}
        tool = object()

        monkeypatch.setattr(
            "EvoScientist.mcp.client.load_mcp_config",
            lambda: {"srv": {"transport": "stdio", "command": "demo"}},
        )

        def fake_load_mcp_tools():
            calls["load"] += 1
            return {"main": [tool]}

        monkeypatch.setattr("EvoScientist.mcp.load_mcp_tools", fake_load_mcp_tools)

        first = agent_module._load_mcp_tools_cached()
        second = agent_module._load_mcp_tools_cached()

        assert calls["load"] == 1
        assert first == second
        assert first is not second
        assert first["main"] is not second["main"]

    def test_reload_when_config_changes(self, monkeypatch):
        calls = {"load": 0}
        state = {"cfg": {"srv": {"transport": "stdio", "command": "v1"}}}

        def fake_load_config():
            return state["cfg"]

        def fake_load_mcp_tools():
            calls["load"] += 1
            return {"main": [f"tool-v{calls['load']}"]}

        monkeypatch.setattr("EvoScientist.mcp.client.load_mcp_config", fake_load_config)
        monkeypatch.setattr("EvoScientist.mcp.load_mcp_tools", fake_load_mcp_tools)

        first = agent_module._load_mcp_tools_cached()
        state["cfg"] = {"srv": {"transport": "stdio", "command": "v2"}}
        second = agent_module._load_mcp_tools_cached()

        assert calls["load"] == 2
        assert first != second
