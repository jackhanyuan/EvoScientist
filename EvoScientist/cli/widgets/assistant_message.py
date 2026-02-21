"""Assistant message widget with incremental Markdown rendering."""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import Markdown


class AssistantMessage(Vertical):
    """Displays the assistant's final Markdown response.

    Mount once, then call :meth:`append_content` for each text chunk.
    When streaming finishes, call :meth:`stop_stream`.

    Each ``append_content`` call re-renders only *this* widget's Markdown —
    not the entire chat history — which is the core improvement over the
    old "rebuild Rich Group every 100 ms" approach.
    """

    DEFAULT_CSS = """
    AssistantMessage {
        height: auto;
        margin: 1 0 0 0;
    }
    AssistantMessage Markdown {
        margin: 0;
        padding: 0;
    }
    """

    def __init__(self, initial_content: str = "") -> None:
        super().__init__()
        self._content = initial_content

    def compose(self):
        yield Markdown("")

    def on_mount(self) -> None:
        if self._content:
            self.query_one(Markdown).update(self._content)

    async def append_content(self, text: str) -> None:
        """Append text and re-render the Markdown widget."""
        self._content += text
        self.query_one(Markdown).update(self._content)

    async def stop_stream(self) -> None:
        """Finalize the stream — ensure final content is rendered."""
        if self._content:
            self.query_one(Markdown).update(self._content)
