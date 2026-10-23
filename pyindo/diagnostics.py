from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpan:
  start: int
  end: int
  line: int
  column: int
  end_line: int
  end_column: int

  def through(self, other: "SourceSpan") -> "SourceSpan":
    """
    Cover two ordered spans without changing their source-coordinate units.
    """

    return SourceSpan(
      self.start, other.end, self.line, self.column,
      other.end_line, other.end_column,
    )


class SourceMap:
  """
  Map absolute character offsets to one-based Unicode line/column positions.
  """

  def __init__(self, source_text: str):
    self.line_starts = [0]
    self.line_starts.extend(
      index + 1 for index, character in enumerate(source_text) if character == "\n"
    )

  def span(self, start: int, end: int) -> SourceSpan:
    start_line = bisect_right(self.line_starts, start) - 1
    end_line = bisect_right(self.line_starts, end) - 1

    return SourceSpan(
      start, end, start_line + 1, start - self.line_starts[start_line] + 1,
      end_line + 1, end - self.line_starts[end_line] + 1,
    )


class PyIndoError(Exception):
  """
  Carry a user-facing compilation error without printing or terminating.
  """

  def __init__(self, message: str, span: SourceSpan | None = None):
    super().__init__(message)
    self.message = message
    self.span = span


def format_error(error: PyIndoError) -> str:
  """
  Render a stable diagnostic; the CLI owns output and process status.
  """

  location = f" (on line number {error.span.line})" if error.span else ""

  return f"Error: {error.message}{location}"
