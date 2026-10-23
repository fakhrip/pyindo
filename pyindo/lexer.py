import codecs
from dataclasses import dataclass
from enum import Enum, auto
from string import ascii_letters, digits

from pyindo.diagnostics import PyIndoError, SourceMap, SourceSpan


class TokenKind(Enum):
  NAME = auto()
  KEYWORD = auto()
  NUMBER = auto()
  BOOLEAN = auto()
  STRING = auto()
  SYMBOL = auto()
  EOF = auto()
  ERROR = auto()


@dataclass(frozen=True)
class StringText:
  text: str
  span: SourceSpan


@dataclass(frozen=True)
class StringExpression:
  span: SourceSpan


@dataclass(frozen=True)
class StringError:
  error: PyIndoError


@dataclass(frozen=True)
class Token:
  kind: TokenKind
  text: str
  value: object
  span: SourceSpan


KEYWORDS = {
  "fungsi", "variabel", "konstanta", "hasilkan", "jika", "selainnya",
  "adalah", "bukan", "maka", "untuk", "selama", "berhenti", "lewati",
  "cocokkan", "hapus", "tidak", "dan", "atau", "didalam",
}
BOOLEAN_VALUES = {"benar": True, "BENAR": True, "salah": False, "SALAH": False}
IDENTIFIER_START = ascii_letters + "_"
IDENTIFIER_BODY = IDENTIFIER_START + digits
SYMBOLS = sorted({
  "<<=", ">>=", "**=", "<=", ">=", "==", "!=", "**", "<<", ">>",
  "+=", "-=", "*=", "/=", "%=", "&=", "|=", "++", "--", "&&", "||",
  "+", "-", "*", "/", "%", "&", "|", "<", ">", "!", "=", ";", ",",
  "(", ")", "{", "}", "[", "]", ":",
}, key=len, reverse=True)


class Lexer:
  """
  Tokenize one source region while retaining absolute source positions.

  String text owns escape decoding. Interpolation keeps undecoded source
  spans so the expression parser can reuse this lexer without moving offsets.
  """

  def __init__(self, source_text: str, start: int, end: int):
    self.source_text = source_text
    self.position = start
    self.end = end
    self.source_map = SourceMap(source_text)
    self.defer_errors = False

  def error(self, message: str, start: int) -> PyIndoError:
    return PyIndoError(message, self.source_map.span(start, min(start + 1, self.end)))

  def skip_comment(self) -> bool:
    """
    Skip one outside-string comment while retaining validation of embedded NULs.
    """

    if self.source_text.startswith("//", self.position, self.end):
      line_end = self.source_text.find("\n", self.position, self.end)
      comment_end = self.end if line_end == -1 else line_end
      nul_position = self.source_text.find("\0", self.position, comment_end)

      if nul_position != -1:
        raise self.error("Unexpected NUL character", nul_position)

      self.position = comment_end
      return True

    if self.source_text.startswith("/*", self.position, self.end):
      comment_start = self.position
      comment_end = self.source_text.find("*/", self.position + 2, self.end)

      if comment_end == -1:
        raise self.error("Unterminated block comment", comment_start)

      nul_position = self.source_text.find("\0", self.position, comment_end)

      if nul_position != -1:
        raise self.error("Unexpected NUL character", nul_position)

      self.position = comment_end + 2
      return True

    return False

  def scan_escape(self) -> str:
    """
    Consume exactly one escape; unknown sequences keep their backslash.
    """

    escape_start = self.position
    self.position += 1

    if self.position >= self.end:
      raise self.error("Unterminated string", escape_start)

    character = self.source_text[self.position]

    if character in "\r\n\0":
      raise self.error("Unexpected newline or NUL in string", self.position)

    self.position += 1

    if character == "$" and self.source_text.startswith("{", self.position, self.end):
      self.position += 1
      return "${"

    if character in ("x", "u", "U"):
      width = {"x": 2, "u": 4, "U": 8}[character]
      self.position = min(self.position + width, self.end)
    elif character == "N" and self.source_text.startswith("{", self.position, self.end):
      closing_brace = self.source_text.find("}", self.position, self.end)

      if closing_brace == -1:
        raise self.error("Invalid Unicode escape", escape_start)

      self.position = closing_brace + 1
    elif character in "01234567":
      for _ in range(2):
        if self.position < self.end and self.source_text[self.position] in "01234567":
          self.position += 1
    elif character not in "\\'\"abfnrtv":
      return self.source_text[escape_start:self.position]

    try:
      return codecs.decode(self.source_text[escape_start:self.position], "unicode-escape")
    except (UnicodeError, ValueError) as escape_error:
      raise self.error("Invalid string escape", escape_start) from escape_error

  def scan_interpolation(self) -> SourceSpan:
    """
    Find the matching brace without treating quoted/comment braces as syntax.
    """

    expression_start = self.position
    brace_depth = 1

    while self.position < self.end:
      character = self.source_text[self.position]

      if character in "\"'":
        self.scan_string()
        continue

      if self.skip_comment():
        continue

      if character == "\0":
        raise self.error("Unexpected NUL character", self.position)

      if character == "{":
        brace_depth += 1
      elif character == "}":
        brace_depth -= 1

        if brace_depth == 0:
          expression_span = self.source_map.span(expression_start, self.position)
          self.position += 1
          return expression_span

      self.position += 1

    raise self.error("Unterminated interpolation", expression_start)

  def scan_string(self) -> tuple[StringText | StringExpression | StringError, ...]:
    """
    Decode literal text once and retain source regions for embedded expressions.
    """

    quote_start = self.position
    quote = self.source_text[self.position]
    self.position += 1
    text_start = self.position
    text_parts = []
    parts = []

    while self.position < self.end:
      character = self.source_text[self.position]

      try:
        if character == quote or self.source_text.startswith("${", self.position, self.end):
          if text_parts:
            parts.append(StringText(
              "".join(text_parts), self.source_map.span(text_start, self.position),
            ))
            text_parts = []

          if character == quote:
            self.position += 1
            return tuple(parts)

          self.position += 2
          parts.append(StringExpression(self.scan_interpolation()))
          text_start = self.position
        elif character == "\\":
          text_parts.append(self.scan_escape())
        elif character in "\r\n\0":
          raise self.error("Unexpected newline or NUL in string", self.position)
        else:
          text_parts.append(character)
          self.position += 1
      except PyIndoError as error:
        if not self.defer_errors:
          raise

        # Preserve earlier interpolation parts before reporting later text errors.
        # Recovery is for diagnostics only; StringError can never become an AST.
        parts.append(StringError(error))
        text_parts = []
        self.position = max(self.position, error.span.end)
        text_start = self.position

    error = self.error("Unterminated string", quote_start)

    if not self.defer_errors:
      raise error

    return tuple([*parts, StringError(error)])

  def tokens(self, *, defer_errors: bool = False) -> list[Token]:
    """
    Optionally retain a lexical error after its valid prefix for parser ordering.

    Standalone tokenization still raises immediately. The parser reaches a
    deferred error only after checking earlier tokens for syntax errors.
    """

    tokens = []
    self.defer_errors = defer_errors

    try:
      self.scan_tokens(tokens)
    except PyIndoError as error:
      if not defer_errors:
        raise

      tokens.append(Token(TokenKind.ERROR, "", error, error.span))

    return tokens

  def scan_tokens(self, tokens: list[Token]) -> None:

    while self.position < self.end:
      character = self.source_text[self.position]

      if character.isspace():
        self.position += 1
        continue

      if self.skip_comment():
        continue

      token_start = self.position

      if character in IDENTIFIER_START:
        self.position += 1

        while self.position < self.end and self.source_text[self.position] in IDENTIFIER_BODY:
          self.position += 1

        value = self.source_text[token_start:self.position]
        kind = TokenKind.KEYWORD if value in KEYWORDS else TokenKind.NAME

        if value in BOOLEAN_VALUES:
          kind, value = TokenKind.BOOLEAN, BOOLEAN_VALUES[value]
      elif character in digits:
        self.position += 1

        while self.position < self.end and self.source_text[self.position] in IDENTIFIER_BODY + ".":
          self.position += 1

        number_text = self.source_text[token_start:self.position]

        if any(letter in IDENTIFIER_START for letter in number_text):
          raise self.error(f"Illegal identifier name: {number_text}", token_start)

        number_parts = number_text.split(".")

        if len(number_parts) > 2 or any(not part for part in number_parts):
          raise self.error(f"Invalid numeric literal: {number_text}", token_start)

        kind = TokenKind.NUMBER
        try:
          value = float(number_text) if len(number_parts) == 2 else int(number_text)
        except ValueError as conversion_error:
          raise self.error("Numeric literal is too large or invalid", token_start) from conversion_error
      elif character in "\"'":
        kind, value = TokenKind.STRING, self.scan_string()
      else:
        symbol = next((
          symbol for symbol in SYMBOLS
          if self.source_text.startswith(symbol, self.position, self.end)
        ), None)

        if symbol is None:
          raise self.error(f"Unexpected character: {character!r}", token_start)

        self.position += len(symbol)
        kind, value = TokenKind.SYMBOL, symbol

      tokens.append(Token(
        kind, self.source_text[token_start:self.position], value,
        self.source_map.span(token_start, self.position),
      ))

    tokens.append(Token(TokenKind.EOF, "", None, self.source_map.span(self.end, self.end)))


def tokenize(source_text: str, *, start: int = 0, end: int | None = None) -> list[Token]:
  """
  Return tokens and one EOF for the requested absolute source region.
  """

  return Lexer(source_text, start, len(source_text) if end is None else end).tokens()
