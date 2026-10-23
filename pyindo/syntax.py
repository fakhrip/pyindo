from pyindo.diagnostics import PyIndoError
from pyindo.lexer import Lexer, StringExpression, StringText, TokenKind
from pyindo.nodes import (
  Assignment, Binary, Call, CallStatement, Declaration, Function, If,
  InterpolatedString, Literal, Name, Parameter, Program, Return, Unary,
)


COMPARISONS = {"==", "!=", "<", "<=", ">", ">=", "adalah", "bukan"}
BINDING_POWER = {
  **{operator: (10, 11) for operator in COMPARISONS},
  "|": (20, 21), "&": (25, 26), "<<": (30, 31), ">>": (30, 31),
  "+": (40, 41), "-": (40, 41),
  "*": (50, 51), "/": (50, 51), "%": (50, 51),
  "**": (70, 60),
}
UNSUPPORTED = {
  "maka", "untuk", "selama", "berhenti", "lewati", "cocokkan", "hapus",
  "tidak", "dan", "atau", "didalam", "&&", "||", "!", ":", "[", "]",
  "+=", "-=", "*=", "/=", "%=", "**=", "&=", "|=", "<<=", ">>=", "++", "--",
}


class Parser:
  """
  Parse token regions into source-aware nodes without emitting bytecode.

  Every block consumes its own closing brace. Expression parsing owns
  precedence, while interpolation uses a bounded parser over the same source.
  """

  def __init__(self, source_text: str, *, start: int = 0, end: int | None = None):
    self.source_text = source_text
    lexer = Lexer(source_text, start, len(source_text) if end is None else end)
    self.tokens = lexer.tokens(defer_errors=True)
    self.position = 0

  @property
  def current(self):
    token = self.tokens[self.position]

    if token.kind == TokenKind.ERROR:
      raise token.value

    return token

  def advance(self):
    token = self.current
    self.position += 1
    return token

  def match(self, text: str) -> bool:
    if self.current.text != text:
      return False

    self.advance()
    return True

  def expected(self, description: str) -> PyIndoError:
    token = self.current

    if token.text in UNSUPPORTED:
      return PyIndoError(f"Unsupported syntax: {token.text!r}", token.span)

    if token.kind == TokenKind.EOF:
      message = f"Expecting {description} but have reached the End Of File"
    else:
      message = f"Expecting {description} but got {token.text!r}"

    return PyIndoError(message, token.span)

  def expect(self, text: str):
    if self.current.text != text:
      raise self.expected(repr(text))

    return self.advance()

  def expect_name(self, description: str = "identifier"):
    if self.current.kind != TokenKind.NAME:
      raise self.expected(description)

    return self.advance()

  def parse_function(self) -> Function:
    """
    Parse an untyped positional signature and its braced function body.
    """

    opening = self.expect("fungsi")
    name = self.expect_name()
    self.expect("(")
    parameters = []

    if self.current.text != ")":
      while True:
        parameter = self.expect_name("parameter name or ')'")
        parameters.append(Parameter(parameter.text, parameter.span))

        if not self.match(","):
          break

    self.expect(")")
    body, closing = self.parse_block()

    return Function(
      name.text, parameters, body, opening.span.through(closing.span), name_span=name.span,
    )

  def parse_block(self):
    """
    Consume one complete block, reporting an unclosed brace at the real EOF.
    """

    self.expect("{")
    body = []

    while self.current.text != "}":
      if self.current.kind == TokenKind.EOF:
        raise self.expected("'}'")

      body.append(self.parse_statement())

    return body, self.expect("}")

  def parse_statement(self):
    """
    Select a statement form and consume its required terminator or owned block.
    """

    opening = self.current

    if opening.text in ("variabel", "konstanta"):
      self.advance()
      name = self.expect_name()
      self.expect("=")
      value = self.parse_expression()
      closing = self.expect(";")

      return Declaration(
        name.text, value, opening.text == "konstanta",
        opening.span.through(closing.span),
      )

    if self.match("hasilkan"):
      value = None if self.current.text == ";" else self.parse_expression()
      closing = self.expect(";")
      return Return(value, opening.span.through(closing.span))

    if opening.text == "jika":
      return self.parse_if()

    if opening.kind == TokenKind.NAME and self.tokens[self.position + 1].text == "=":
      self.advance()
      self.advance()
      value = self.parse_expression()
      closing = self.expect(";")
      return Assignment(opening.text, value, opening.span.through(closing.span))

    expression = self.parse_expression()

    if not isinstance(expression, Call):
      raise self.expected("assignment or function call")

    closing = self.expect(";")
    return CallStatement(expression, opening.span.through(closing.span))

  def parse_if(self) -> If:
    """
    Consume a complete conditional chain; nested blocks own their else arms.
    """

    opening = self.expect("jika")
    branches = []
    else_body = None

    while True:
      self.expect("(")
      condition = self.parse_expression()
      self.expect(")")
      body, closing = self.parse_block()
      branches.append((condition, body))

      if not self.match("selainnya"):
        break

      if self.match("jika"):
        continue

      else_body, closing = self.parse_block()
      break

    return If(branches, else_body, opening.span.through(closing.span))

  def parse_expression(self, minimum_power: int = 0):
    """
    Parse with binding powers; power binds above a left unary sign, below a right one.
    """

    opening = self.current

    if opening.text in ("+", "-"):
      self.advance()
      operand = self.parse_expression(60)
      expression = Unary(opening.text, operand, opening.span.through(operand.span))
    else:
      expression = self.parse_primary()

    compared = False

    while self.current.text in BINDING_POWER:
      operator = self.current
      left_power, right_power = BINDING_POWER[operator.text]

      if left_power < minimum_power:
        break

      if operator.text in COMPARISONS:
        if compared:
          raise PyIndoError("Chained comparisons are not supported", operator.span)

        compared = True

      self.advance()
      right = self.parse_expression(right_power)
      symbol = {"adalah": "==", "bukan": "!="}.get(operator.text, operator.text)
      expression = Binary(symbol, expression, right, expression.span.through(right.span))

    return expression

  def parse_primary(self):
    """
    Parse one literal, grouped expression, local name, or direct named call.
    """

    token = self.current

    if self.match("("):
      expression = self.parse_expression()
      self.expect(")")
      return expression

    if token.kind in (TokenKind.NUMBER, TokenKind.BOOLEAN):
      self.advance()
      return Literal(token.value, token.span)

    if token.kind == TokenKind.STRING:
      self.advance()
      return self.parse_string(token)

    if token.kind == TokenKind.NAME:
      self.advance()

      if not self.match("("):
        return Name(token.text, token.span)

      arguments = []

      if self.current.text != ")":
        while True:
          arguments.append(self.parse_expression())

          if not self.match(","):
            break

      closing = self.expect(")")
      return Call(token.text, arguments, token.span.through(closing.span))

    raise self.expected("expression")

  def parse_string(self, token):
    """
    Reparse interpolation regions against their original absolute source offsets.
    """

    parts = []
    has_expression = False

    for part in token.value:
      if isinstance(part, StringText):
        parts.append(part.text)
      elif isinstance(part, StringExpression):
        parser = Parser(self.source_text, start=part.span.start, end=part.span.end)
        parts.append(parser.parse_expression())
        has_expression = True

        if parser.current.kind != TokenKind.EOF:
          raise parser.expected("end of interpolation")

    if has_expression:
      return InterpolatedString(parts, token.span)

    return Literal("".join(parts), token.span)


def parse_module(source_text: str) -> Program:
  """
  Parse top-level function declarations; semantic validation follows separately.
  """

  parser = Parser(source_text)
  functions = []

  while parser.current.kind != TokenKind.EOF:
    functions.append(parser.parse_function())

  return Program(functions, source_text, parser.tokens[0].span.through(parser.current.span))
