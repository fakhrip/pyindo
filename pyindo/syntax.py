from dataclasses import replace

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, PyIndoError, SourceMap
from pyindo.lexer import Lexer, StringError, StringExpression, StringText, TokenKind
from pyindo.nodes import (
  Assignment, AugmentedAssignment, Binary, Break, Call, CallStatement, Conditional, Continue,
  Declaration, Delete, For, ForEach, Function, If, Index, IndexedAssignment, InterpolatedString,
  ListLiteral, Literal, Logical, Name, NonEmpty,
  Parameter, Program, Return, TypeAnnotation, Unary, While,
)


COMPARISONS = {"==", "!=", "<", "<=", ">", ">=", "adalah", "bukan", "didalam"}
AUGMENTED_OPERATORS = {"+=", "-=", "*=", "/=", "%=", "**=", "&=", "|=", "<<=", ">>="}
BINDING_POWER = {
  "atau": (2, 3), "||": (2, 3), "dan": (4, 5), "&&": (4, 5),
  **{operator: (10, 11) for operator in COMPARISONS},
  "|": (20, 21), "&": (25, 26), "<<": (30, 31), ">>": (30, 31),
  "+": (40, 41), "-": (40, 41),
  "*": (50, 51), "/": (50, 51), "%": (50, 51),
  "**": (70, 60),
}
UNSUPPORTED = {
  "cocokkan",
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
    Parse a mandatory typed positional signature and its braced function body.
    """

    opening = self.expect("fungsi")
    name = self.expect_name()
    self.expect("(")
    parameters = []

    if self.current.text != ")":
      while True:
        parameter = self.expect_name("parameter name or ')'")
        self.expect(":")
        annotation = self.parse_type_annotation()
        parameters.append(Parameter(parameter.text, parameter.span, annotation))

        if not self.match(","):
          break

    self.expect(")")
    self.expect(":")
    return_annotation = self.parse_type_annotation()
    body, closing = self.parse_block()

    return Function(
      name.text, parameters, body, opening.span.through(closing.span), name_span=name.span,
      return_annotation=return_annotation,
    )

  def parse_type_annotation(self) -> TypeAnnotation:
    """
    Read contextual type names without reserving them in ordinary expressions.
    """

    name = self.expect_name("type name")
    arguments = []
    closing = name

    if self.match("<"):
      arguments.append(self.parse_type_annotation())
      closing = self.consume_type_close()

    return TypeAnnotation(name.text, arguments, name.span.through(closing.span))

  def consume_type_close(self):
    """
    Peel one generic closer, retaining a located operator remainder in the cursor.
    """

    token = self.current
    if token.text not in (">", ">=", ">>", ">>="):
      raise self.expected("'>'")

    source_map = SourceMap(self.source_text)
    closer = replace(token, text=">", value=">", span=source_map.span(token.span.start, token.span.start + 1))
    if len(token.text) == 1:
      self.advance()
    else:
      remainder = token.text[1:]
      self.tokens[self.position] = replace(
        token, text=remainder, value=remainder,
        span=source_map.span(token.span.start + 1, token.span.end),
      )
    return closer

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

    if self.match("hasilkan"):
      value = None if self.current.text == ";" else self.parse_expression()
      closing = self.expect(";")
      return Return(value, opening.span.through(closing.span))

    if opening.text == "jika":
      return self.parse_if()

    if opening.text == "selama":
      return self.parse_while()

    if opening.text == "untuk":
      return self.parse_for()

    if opening.text in ("berhenti", "lewati"):
      self.advance()
      closing = self.expect(";")
      node_type = Break if opening.text == "berhenti" else Continue
      return node_type(opening.span.through(closing.span))

    statement = self.parse_simple_statement()
    closing = self.expect(";")

    return replace(statement, span=opening.span.through(closing.span))

  def parse_simple_statement(self, *, allow_declaration: bool = True):
    """
    Parse a write, indexed deletion, or call; the caller owns its delimiter.
    """

    opening = self.current

    if self.match("hapus"):
      target = self.parse_expression()

      if not isinstance(target, Index):
        raise PyIndoError("Deletion requires an indexed target", target.span)

      return Delete(target, opening.span.through(target.span))

    if opening.text in ("variabel", "konstanta"):
      if not allow_declaration:
        raise PyIndoError("Declaration is not allowed in this header slot", opening.span)

      opening, name, annotation = self.parse_binding_header()
      self.expect("=")
      value = self.parse_expression()
      return Declaration(
        name.text, value, opening.text == "konstanta", opening.span.through(value.span),
        annotation,
      )

    if opening.kind == TokenKind.NAME:
      operator = self.tokens[self.position + 1]

      if operator.text in {"=", "++", "--"} | AUGMENTED_OPERATORS:
        self.advance()
        self.advance()

        if operator.text in ("++", "--"):
          # Postfix updates are statements, never expression-valued operators.
          symbol = "+" if operator.text == "++" else "-"
          return AugmentedAssignment(
            opening.text, symbol, Literal(1, operator.span), opening.span.through(operator.span),
          )

        value = self.parse_expression()
        span = opening.span.through(value.span)

        if operator.text == "=":
          return Assignment(opening.text, value, span)

        return AugmentedAssignment(opening.text, operator.text[:-1], value, span)

    expression = self.parse_expression()

    if isinstance(expression, Index) and self.match("="):
      value = self.parse_expression()
      return IndexedAssignment(expression, value, opening.span.through(value.span))

    if not isinstance(expression, Call):
      raise self.expected("assignment or function call")

    return CallStatement(expression, expression.span)

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
      body, closing_span = self.parse_if_arm()
      branches.append((condition, body))

      if not self.match("selainnya"):
        break

      if self.match("jika"):
        continue

      else_body, closing_span = self.parse_if_arm()
      break

    return If(branches, else_body, opening.span.through(closing_span))

  def parse_if_arm(self):
    """
    Parse braces or one simple maka statement without a dangling-else ambiguity.

    Compound statements need braces; only this enclosing chain may consume
    a following else arm. Loop bodies keep their separate braced grammar.
    """

    if self.current.text == "{":
      body, closing = self.parse_block()
      return body, closing.span

    self.expect("maka")

    if self.current.text in ("jika", "selama", "untuk", "{"):
      raise self.expected("simple statement after 'maka'")

    statement = self.parse_statement()
    return [statement], statement.span

  def parse_while(self) -> While:
    """
    Parse a nonempty while condition and a body that owns its closing brace.
    """

    opening = self.expect("selama")
    self.expect("(")
    condition = self.parse_expression()
    self.expect(")")
    body, closing = self.parse_block()

    return While(condition, body, opening.span.through(closing.span))

  def parse_binding_header(self):
    """
    Read a declaration prefix once, preserving any split generic closing tokens.
    """

    opening = self.advance()
    name = self.expect_name()
    self.expect(":")
    return opening, name, self.parse_type_annotation()

  def parse_for(self) -> For | ForEach:
    """
    Distinguish iterator and C-style headers without rewinding parsed type tokens.
    """

    opening = self.expect("untuk")
    self.expect("(")
    initializer = None

    if self.current.text in ("variabel", "konstanta"):
      binding, name, annotation = self.parse_binding_header()

      if self.match("didalam"):
        iterable = self.parse_expression()
        self.expect(")")
        body, closing = self.parse_block()
        return ForEach(
          name.text, annotation, binding.text == "konstanta", iterable, body,
          opening.span.through(closing.span), binding.span.through(annotation.span),
        )

      self.expect("=")
      value = self.parse_expression()
      initializer = Declaration(
        name.text, value, binding.text == "konstanta", binding.span.through(value.span), annotation,
      )
    elif self.current.text != ";":
      initializer = self.parse_simple_statement()

    self.expect(";")
    condition = None if self.current.text == ";" else self.parse_expression()
    self.expect(";")
    update = (
      None if self.current.text == ")"
      else self.parse_simple_statement(allow_declaration=False)
    )
    self.expect(")")
    body, closing = self.parse_block()

    return For(initializer, condition, update, body, opening.span.through(closing.span))

  def is_nonempty_operator(self) -> bool:
    """
    Recognize a contextual token pair without reserving the identifier kosong.
    """

    return (
      self.current.text == "tidak"
      and self.tokens[self.position + 1].text == "kosong"
    )

  def parse_expression(self, minimum_power: int = 0):
    """
    Parse with binding powers; power binds above a left unary sign, below a right one.
    """

    opening = self.current

    if opening.text in ("tidak", "!"):
      if minimum_power > 6:
        raise self.expected("parenthesized logical negation")

      self.advance()
      operand = self.parse_expression(6)
      expression = Unary("not", operand, opening.span.through(operand.span))
    elif opening.text in ("+", "-"):
      self.advance()
      operand = self.parse_expression(60)
      expression = Unary(opening.text, operand, opening.span.through(operand.span))
    else:
      expression = self.parse_postfix()

    compared = False

    while self.current.text in BINDING_POWER or self.is_nonempty_operator():
      operator = self.current
      nonempty = self.is_nonempty_operator()
      left_power, right_power = (10, 11) if nonempty else BINDING_POWER[operator.text]

      if left_power < minimum_power:
        break

      if operator.text in COMPARISONS or nonempty:
        if compared:
          raise PyIndoError("Chained comparisons are not supported", operator.span)

        compared = True

      if nonempty:
        self.advance()
        closing = self.advance()
        expression = NonEmpty(expression, expression.span.through(closing.span))

        # The phrase ends its comparison operand; arithmetic needs grouping.
        following_power = BINDING_POWER.get(self.current.text)
        if following_power is not None and following_power[0] > 10:
          raise self.expected("parenthesized nonempty predicate before arithmetic")

        continue

      self.advance()
      right = self.parse_expression(right_power)
      span = expression.span.through(right.span)

      if operator.text in ("dan", "&&", "atau", "||"):
        symbol = "and" if operator.text in ("dan", "&&") else "or"
        expression = Logical(symbol, expression, right, span)
      else:
        symbol = {"adalah": "==", "bukan": "!=", "didalam": "in"}.get(operator.text, operator.text)
        expression = Binary(symbol, expression, right, span)

    if minimum_power <= 1 and self.match("jika"):
      # Only the false arm associates right without explicit grouping.
      condition = self.parse_expression(2)
      self.expect("selainnya")
      false_value = self.parse_expression(1)
      expression = Conditional(
        expression, condition, false_value, expression.span.through(false_value.span),
      )

    return expression

  def parse_postfix(self):
    """
    Attach index suffixes to one primary without introducing callable expressions.
    """

    expression = self.parse_primary()

    while self.match("["):
      index = self.parse_expression()
      closing = self.expect("]")
      expression = Index(expression, index, expression.span.through(closing.span))

    return expression

  def parse_list(self) -> ListLiteral:
    """
    Own a fresh list display and permit one trailing comma between its brackets.
    """

    opening = self.expect("[")
    items = []

    if self.current.text != "]":
      while True:
        items.append(self.parse_expression())

        if not self.match(",") or self.current.text == "]":
          break

    closing = self.expect("]")
    return ListLiteral(items, opening.span.through(closing.span))

  def parse_primary(self):
    """
    Parse one literal, grouped expression, local name, or direct named call.
    """

    token = self.current

    if token.text == "[":
      return self.parse_list()

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
      if isinstance(part, StringError):
        raise part.error
      elif isinstance(part, StringText):
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

  parser = None

  try:
    parser = Parser(source_text)
    functions = []

    while parser.current.kind != TokenKind.EOF:
      functions.append(parser.parse_function())

    return Program(functions, source_text, parser.tokens[0].span.through(parser.current.span))
  except RecursionError as complexity_error:
    span = parser.current.span if parser is not None else SourceMap(source_text).span(0, 0)
    raise PyIndoError(COMPLEXITY_ERROR_MESSAGE, span) from complexity_error
