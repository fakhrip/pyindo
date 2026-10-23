from dataclasses import dataclass

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, PyIndoError, SourceSpan
from pyindo.nodes import (
  Assignment, Binary, Call, CallStatement, Declaration, If,
  InterpolatedString, Literal, Logical, Name, Program, Return, Unary,
)


RESERVED_FUNCTION_NAMES = {"tampilkan", "print", "__name__", "__file__", "__builtins__"}


@dataclass(frozen=True)
class FunctionSignature:
  name: str
  parameters: list[str]
  span: SourceSpan


@dataclass(frozen=True)
class FunctionScope:
  name: str
  parameters: list[str]
  local_names: list[str]
  constant_names: set[str]


@dataclass(frozen=True)
class ProgramSymbols:
  signatures: dict[str, FunctionSignature]
  scopes: dict[str, FunctionScope]


def _declarations(body):
  for statement in body:
    if isinstance(statement, Declaration):
      yield statement
    elif isinstance(statement, If):
      for _, branch_body in statement.branches:
        yield from _declarations(branch_body)

      if statement.else_body is not None:
        yield from _declarations(statement.else_body)


class FunctionAnalyzer:
  """
  Validate one function with a fixed binding table and path-local initialization.

  Binding collection and source-order checking are separate: a known local
  slot never implies that a declaration on another path has executed.
  """

  def __init__(self, scope: FunctionScope, signatures: dict[str, FunctionSignature]):
    self.scope = scope
    self.signatures = signatures
    self.local_names = set(scope.local_names)

  def require_initialized(self, name: str, span: SourceSpan, initialized: set[str]):
    if name not in self.local_names:
      raise PyIndoError(f"Identifier '{name}' has not declared yet", span)

    if name not in initialized:
      raise PyIndoError(f"Identifier '{name}' is not initialized", span)

  def expression(self, expression, initialized: set[str]):
    """
    Check every operand and argument without executing or inferring its value.
    """

    if isinstance(expression, Literal):
      return

    if isinstance(expression, Name):
      self.require_initialized(expression.identifier, expression.span, initialized)
    elif isinstance(expression, Unary):
      self.expression(expression.operand, initialized)
    elif isinstance(expression, (Binary, Logical)):
      # Runtime laziness never hides invalid bindings or calls from analysis.
      self.expression(expression.left, initialized)
      self.expression(expression.right, initialized)
    elif isinstance(expression, Call):
      if expression.callee != "tampilkan":
        signature = self.signatures.get(expression.callee)

        if signature is None:
          raise PyIndoError(f"Unknown function: {expression.callee}", expression.span)

        if len(expression.arguments) != len(signature.parameters):
          raise PyIndoError(
            f"Function '{expression.callee}' expects {len(signature.parameters)} arguments, "
            f"got {len(expression.arguments)}", expression.span,
          )

      for argument in expression.arguments:
        self.expression(argument, initialized)
    elif isinstance(expression, InterpolatedString):
      for part in expression.parts:
        if not isinstance(part, str):
          self.expression(part, initialized)
    else:
      raise TypeError(f"Unknown expression node: {type(expression).__name__}")

  def block(self, body, initialized: set[str]) -> tuple[set[str], bool]:
    """
    Return initialized names and whether the block can reach its successor.

    Continue validating unreachable source, but retain its terminated state
    so it cannot add initialized names to a live branch merge.
    """

    initialized = set(initialized)
    can_fall_through = True

    for statement in body:
      if isinstance(statement, Declaration):
        self.expression(statement.value, initialized)
        initialized.add(statement.name)
      elif isinstance(statement, Assignment):
        self.require_initialized(statement.target, statement.span, initialized)

        if statement.target in self.scope.constant_names:
          raise PyIndoError(f"Cannot reassign constant '{statement.target}'", statement.span)

        self.expression(statement.value, initialized)
      elif isinstance(statement, Return):
        if statement.value is not None:
          self.expression(statement.value, initialized)

        can_fall_through = False
      elif isinstance(statement, CallStatement):
        self.expression(statement.call, initialized)
      elif isinstance(statement, If):
        incoming = set(initialized)
        falling_states = []

        for condition, branch_body in statement.branches:
          self.expression(condition, incoming)
          branch_state, branch_falls = self.block(branch_body, incoming)

          if branch_falls:
            falling_states.append(branch_state)

        if statement.else_body is None:
          # An absent else leaves a path on which no branch executed.
          falling_states.append(incoming)
        else:
          else_state, else_falls = self.block(statement.else_body, incoming)

          if else_falls:
            falling_states.append(else_state)

        if falling_states:
          initialized = set.intersection(*falling_states)
        else:
          can_fall_through = False
      else:
        raise TypeError(f"Unknown statement node: {type(statement).__name__}")

    return initialized, can_fall_through


def _analyze_program(program: Program) -> ProgramSymbols:
  """
  Register all functions, collect locals, then validate calls and live paths.
  """

  signatures = {}
  scopes = {}

  for function in program.functions:
    if function.name in RESERVED_FUNCTION_NAMES:
      raise PyIndoError(
        f"Function name '{function.name}' is reserved", function.name_span or function.span,
      )

    if function.name in signatures:
      raise PyIndoError(f"Duplicate function: {function.name}", function.span)

    signatures[function.name] = FunctionSignature(
      function.name, [parameter.name for parameter in function.parameters], function.span,
    )

  if "utama" not in signatures:
    raise PyIndoError("Entrypoint is not exist, you should create it first using `utama` function")

  if signatures["utama"].parameters:
    raise PyIndoError("Entrypoint 'utama' must not take arguments", signatures["utama"].span)

  for function in program.functions:
    parameters = signatures[function.name].parameters
    local_names = []
    constant_names = set()
    bindings = [
      (parameter.name, parameter.span, False) for parameter in function.parameters
    ]
    bindings.extend(
      (declaration.name, declaration.span, declaration.is_constant)
      for declaration in _declarations(function.body)
    )

    for name, span, is_constant in bindings:
      if name in signatures or name == "tampilkan":
        raise PyIndoError(f"Local name '{name}' conflicts with a function", span)

      if name in local_names:
        raise PyIndoError(f"Duplicate local declaration: {name}", span)

      local_names.append(name)

      if is_constant:
        constant_names.add(name)

    scope = FunctionScope(function.name, parameters, local_names, constant_names)
    scopes[function.name] = scope
    FunctionAnalyzer(scope, signatures).block(function.body, set(parameters))

  return ProgramSymbols(signatures, scopes)


def analyze_program(program: Program) -> ProgramSymbols:
  """
  Validate bindings and initialization, reporting the compiler's traversal limit.
  """

  try:
    return _analyze_program(program)
  except RecursionError as complexity_error:
    raise PyIndoError(COMPLEXITY_ERROR_MESSAGE, program.span) from complexity_error
