"""Tests for UI backend runtime selection."""

from dataclasses import dataclass

from EvoScientist.cli.tui_runtime import normalize_ui_backend, resolve_ui_backend, run_streaming


def test_normalize_ui_backend_defaults_to_rich():
    assert normalize_ui_backend(None) == "rich"
    assert normalize_ui_backend("") == "rich"


def test_normalize_ui_backend_accepts_known_values():
    assert normalize_ui_backend("rich") == "rich"
    assert normalize_ui_backend("textual") == "textual"
    assert normalize_ui_backend("TeXtUaL") == "textual"


def test_normalize_ui_backend_unknown_falls_back_to_rich():
    assert normalize_ui_backend("unknown-ui") == "rich"


def test_resolve_ui_backend_falls_back_when_textual_unavailable(monkeypatch):
    monkeypatch.setattr("EvoScientist.cli.tui_runtime._has_textual_support", lambda: False)
    assert resolve_ui_backend("textual") == "rich"


def test_resolve_ui_backend_keeps_textual_when_available(monkeypatch):
    monkeypatch.setattr("EvoScientist.cli.tui_runtime._has_textual_support", lambda: True)
    assert resolve_ui_backend("textual") == "textual"


@dataclass
class _BrokenBackend:
    name: str = "textual"

    def run_streaming(self, **kwargs):  # noqa: ANN003, ANN201
        raise RuntimeError("boom")


def test_run_streaming_falls_back_to_rich_on_runtime_error(monkeypatch):
    monkeypatch.setattr("EvoScientist.cli.tui_runtime.get_backend", lambda *a, **k: _BrokenBackend())

    class _RichStub:
        def run_streaming(self, **kwargs):  # noqa: ANN003, ANN201
            return "fallback-ok"

    monkeypatch.setattr("EvoScientist.cli.tui_runtime.RichStreamingBackend", lambda: _RichStub())

    result = run_streaming(
        ui_backend="textual",
        agent=object(),
        message="hello",
        thread_id="t1",
        show_thinking=False,
        interactive=True,
    )
    assert result == "fallback-ok"
