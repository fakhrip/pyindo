from dataclasses import dataclass

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, PyIndoError, SourceSpan
from pyindo.nodes import (
  Assignment, AugmentedAssignment, Binary, Break, Call, CallStatement, Continue,
  Declaration, Delete, For, If, Index, IndexedAssignment, InterpolatedString,
  ListLiteral, Literal, Logical, Name,
  Program, Return, Unary, While,
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


@dataclass
class FlowResult:
  initialized: set[str]
  falls_through: bool
  breaks: set[str] | None = None
  continues: set[str] | None = None


def _meet_exit_states(current: set[str] | None, incoming: set[str] | None) -> set[str] | None:
  """
  Intersect real exit paths; an empty set is a path, while None is absent.
  """

  if current is None:
    return None if incoming is None else set(incoming)

  return set(current) if incoming is None else current & incoming


def _declarations(body):
  """
  Walk source bindings once, including loop headers, in function-local order.
  """

  for statement in body:
    if isinstance(statement, Declaration):
      yield statement
    elif isinstance(statement, If):
      for _, branch_body in statement.branches:
        yield from _declarations(branch_body)

      if statement.else_body is not None:
        yield from _declarations(statement.else_body)
    elif isinstance(statement, For):
      if isinstance(statement.initializer, Declaration):
        yield statement.initializer

      yield from _declarations(statement.body)
    elif isinstance(statement, While):
      yield from _declarations(statement.body)


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
    elif isinstance(expression, ListLiteral):
      for item in expression.items:
        self.expression(item, initialized)
    elif isinstance(expression, Index):
      self.expression(expression.container, initialized)
      self.expression(expression.index, initialized)
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

  def mutation_target(self, target: Index, initialized: set[str]) -> None:
    """
    Check target reads and reject direct constant roots without alias inference.

    Runtime frozen values protect indirect paths. Constants appearing only as
    indices or inside a fresh expression result are not the mutated binding.
    """

    self.expression(target, initialized)
    root = target.container

    while isinstance(root, Index):
      root = root.container

    if isinstance(root, Name) and root.identifier in self.scope.constant_names:
      raise PyIndoError(f"Cannot mutate constant '{root.identifier}'", target.span)

  def block(self, body, initialized: set[str], *, loop_depth: int = 0) -> FlowResult:
    """
    Track live exits separately from the source-order diagnostic cursor.

    Dead suffixes are still checked, but cannot revive fallthrough or add
    break/continue paths to a later loop-update initialization merge.
    """

    flow = FlowResult(set(initialized), True)

    for statement in body:
      statement_flow = self.statement(statement, flow.initialized, loop_depth=loop_depth)

      if flow.falls_through:
        flow.breaks = _meet_exit_states(flow.breaks, statement_flow.breaks)
        flow.continues = _meet_exit_states(flow.continues, statement_flow.continues)
        flow.falls_through = statement_flow.falls_through

      flow.initialized = statement_flow.initialized

    return flow

  def statement(self, statement, initialized: set[str], *, loop_depth: int) -> FlowResult:
    """
    Validate one statement and classify its normal or nearest-loop exits.
    """

    initialized = set(initialized)

    if isinstance(statement, Declaration):
      self.expression(statement.value, initialized)
      initialized.add(statement.name)
    elif isinstance(statement, IndexedAssignment):
      self.expression(statement.value, initialized)
      self.mutation_target(statement.target, initialized)
    elif isinstance(statement, Delete):
      self.mutation_target(statement.target, initialized)
    elif isinstance(statement, (Assignment, AugmentedAssignment)):
      self.require_initialized(statement.target, statement.span, initialized)

      if statement.target in self.scope.constant_names:
        raise PyIndoError(f"Cannot reassign constant '{statement.target}'", statement.span)

      self.expression(statement.value, initialized)
    elif isinstance(statement, Return):
      if statement.value is not None:
        self.expression(statement.value, initialized)

      return FlowResult(initialized, False)
    elif isinstance(statement, CallStatement):
      self.expression(statement.call, initialized)
    elif isinstance(statement, (Break, Continue)):
      if loop_depth == 0:
        keyword = "berhenti" if isinstance(statement, Break) else "lewati"
        raise PyIndoError(f"'{keyword}' is only allowed inside a loop", statement.span)

      return FlowResult(
        initialized, False,
        breaks=initialized if isinstance(statement, Break) else None,
        continues=initialized if isinstance(statement, Continue) else None,
      )
    elif isinstance(statement, If):
      return self.analyze_if(statement, initialized, loop_depth=loop_depth)
    elif isinstance(statement, While):
      self.expression(statement.condition, initialized)
      self.block(statement.body, initialized, loop_depth=loop_depth + 1)
      # A possible zero-iteration path retains only incoming initialization.
      # This loop consumes its own break/continue exits, including nested ones.
    elif isinstance(statement, For):
      return self.analyze_for(statement, initialized, loop_depth=loop_depth)
    else:
      raise TypeError(f"Unknown statement node: {type(statement).__name__}")

    return FlowResult(initialized, True)

  def analyze_if(self, statement: If, initialized: set[str], *, loop_depth: int) -> FlowResult:
    """
    Join normal paths and loop-control exits without counting returning arms.
    """

    branches = []

    for condition, body in statement.branches:
      self.expression(condition, initialized)
      branches.append(self.block(body, initialized, loop_depth=loop_depth))

    branches.append(
      FlowResult(set(initialized), True) if statement.else_body is None
      else self.block(statement.else_body, initialized, loop_depth=loop_depth)
    )
    normal_states = [branch.initialized for branch in branches if branch.falls_through]
    result = FlowResult(
      set.intersection(*normal_states) if normal_states else set(initialized),
      bool(normal_states),
    )

    for branch in branches:
      result.breaks = _meet_exit_states(result.breaks, branch.breaks)
      result.continues = _meet_exit_states(result.continues, branch.continues)

    return result

  def analyze_for(self, statement: For, initialized: set[str], *, loop_depth: int) -> FlowResult:
    """
    Check an update against exactly the body routes that can reach it.

    Breaks and returns skip updates. An empty continue set still represents
    a real route and must never be replaced using a truthiness fallback.
    """

    if statement.initializer is not None:
      initialized = self.statement(
        statement.initializer, initialized, loop_depth=loop_depth,
      ).initialized

    if statement.condition is not None:
      self.expression(statement.condition, initialized)

    body_flow = self.block(statement.body, initialized, loop_depth=loop_depth + 1)
    update_state = body_flow.initialized if body_flow.falls_through else None
    update_state = _meet_exit_states(update_state, body_flow.continues)

    if statement.update is not None:
      # With no live route, preserve source-order checks without inventing one.
      diagnostic_state = body_flow.initialized if update_state is None else update_state
      self.statement(statement.update, diagnostic_state, loop_depth=loop_depth)

    # Initializer runs once; neither a body nor an update is assumed to run.
    return FlowResult(set(initialized), True)


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
