"""Summarization panel widget for context compression display.

Renders a Rich Panel showing that LangGraph's summarization middleware
has compressed older conversation history. Yellow/amber border to
distinguish from the blue thinking panel. Default collapsed; click to
expand/collapse.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from textual.events import Click
from textual.widgets import Static

_MAX_COLLAPSED_CHARS = 80
_MAX_EXPANDED_CHARS = 3000


class SummarizationWidget(Static):
    """Collapsible panel showing context summarization.

    Unlike ThinkingWidget this is not streamed — the full text arrives
    in a single event. Defaults to collapsed with a one-line preview.

    Usage::

        w = SummarizationWidget()
        await container.mount(w)
        w.set_content("The conversation covered ...")
    """

    DEFAULT_CSS = """
    SummarizationWidget {
        height: auto;
        margin: 0 0 1 0;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._content = ""
        self._collapsed = True

    def _char_count_label(self) -> str:
        n = len(self._content)
        if n >= 1000:
            return f"{n / 1000:.1f}k chars"
        return f"{n:,} chars"

    def _refresh_display(self) -> None:
        if not self._content:
            self.update("")
            return

        if self._collapsed:
            title = f"Context Summarized ({self._char_count_label()})"
            first_line = self._content.strip().split("\n")[0].strip()
            if len(first_line) > _MAX_COLLAPSED_CHARS:
                first_line = first_line[:_MAX_COLLAPSED_CHARS - 3] + "\u2026"
            preview = Text(first_line, style="dim italic")
            preview.append("  [click to expand]", style="dim italic")
            body = preview
        else:
            title = f"Context Summarized ({self._char_count_label()})"
            display = self._content.rstrip()
            if len(display) > _MAX_EXPANDED_CHARS:
                half = _MAX_EXPANDED_CHARS // 2
                display = (
                    display[:half]
                    + "\n\n... (truncated) ...\n\n"
                    + display[-half:]
                )
            body = Text(display, style="dim italic") if display else Text(
                "(empty)", style="dim"
            )

        self.update(
            Panel(body, title=title, border_style="#f59e0b", padding=(0, 1))
        )

    def set_content(self, text: str) -> None:
        """Set the summarization text and refresh display."""
        self._content = text
        self._refresh_display()

    def on_click(self, event: Click) -> None:
        """Toggle collapsed/expanded state."""
        if self._content:
            self._collapsed = not self._collapsed
            self._refresh_display()
