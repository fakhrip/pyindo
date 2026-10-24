from dataclasses import dataclass, field

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, PyIndoError, SourceSpan
from pyindo.nodes import (
  Assignment, AugmentedAssignment, Binary, Break, Call, CallStatement, ComparisonChain, Conditional, Continue,
  Declaration, Delete, For, ForEach, If, Index, IndexedAssignment, InterpolatedString,
  ListLiteral, Literal, Logical, ModuleMember, Name, NonEmpty,
  Program, Return, Switch, Unary, While,
)
from pyindo.types import TypeSpec, allows_none, resolve_type


RESERVED_FUNCTION_NAMES = {"tampilkan", "print", "__name__", "__file__", "__builtins__"}


@dataclass(frozen=True)
class FunctionSignature:
  name: str
  parameters: list[str]
  span: SourceSpan
  parameter_types: tuple[TypeSpec, ...] = ()
  return_type: TypeSpec = "apapun"


@dataclass(frozen=True)
class FunctionScope:
  name: str
  parameters: list[str]
  local_names: list[str]
  constant_names: set[str]
  binding_types: dict[str, TypeSpec] = field(default_factory=dict)
  return_type: TypeSpec = "apapun"


@dataclass(frozen=True)
class ValueBinding:
  name: str
  type_spec: TypeSpec
  is_constant: bool
  span: SourceSpan


@dataclass(frozen=True)
class ProgramSymbols:
  signatures: dict[str, FunctionSignature]
  scopes: dict[str, FunctionScope]
  module_values: dict[str, ValueBinding] = field(default_factory=dict)
  imported_values: dict[str, ValueBinding] = field(default_factory=dict)


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


def _join_branches(branches: list[FlowResult], initialized: set[str]) -> FlowResult:
  """
  Join continuing paths and independently intersect real loop-control exits.

  Returning arms do not dilute continuing initialization. Empty exit states
  still represent live paths; only None means that exit was absent.
  """

  normal_states = [branch.initialized for branch in branches if branch.falls_through]
  result = FlowResult(
    set.intersection(*normal_states) if normal_states else set(initialized),
    bool(normal_states),
  )

  for branch in branches:
    result.breaks = _meet_exit_states(result.breaks, branch.breaks)
    result.continues = _meet_exit_states(result.continues, branch.continues)

  return result


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
    elif isinstance(statement, Switch):
      for case in statement.cases:
        yield from _declarations(case.body)

      if statement.else_body is not None:
        yield from _declarations(statement.else_body)
    elif isinstance(statement, For):
      if isinstance(statement.initializer, Declaration):
        yield statement.initializer

      yield from _declarations(statement.body)
    elif isinstance(statement, ForEach):
      yield statement
      yield from _declarations(statement.body)
    elif isinstance(statement, While):
      yield from _declarations(statement.body)


def validate_call_arguments(call: Call, signature: FunctionSignature) -> None:
  """
  Check declared slots without evaluating values or reordering named arguments.

  Keep established diagnostics for ordinary all-positional calls. Keyword labels
  bind to the owner's parameter names even when the function was imported by alias.
  """

  positional_count = len(call.arguments)
  if not call.keywords:
    if positional_count != len(signature.parameters):
      raise PyIndoError(
        f"Function '{call.callee}' expects {len(signature.parameters)} arguments, "
        f"got {positional_count}", call.span,
      )
    return

  if positional_count > len(signature.parameters):
    raise PyIndoError(f"Too many positional arguments for function '{call.callee}'", call.span)

  filled = set(signature.parameters[:positional_count])
  for keyword in call.keywords:
    if keyword.name not in signature.parameters:
      raise PyIndoError(f"Unknown keyword argument '{keyword.name}' for function '{call.callee}'", keyword.span)
    if keyword.name in filled:
      raise PyIndoError(f"Multiple values for argument '{keyword.name}'", keyword.span)
    filled.add(keyword.name)

  for name in signature.parameters:
    if name not in filled:
      raise PyIndoError(f"Missing required argument '{name}' for function '{call.callee}'", call.span)


class FunctionAnalyzer:
  """
  Validate one function with a fixed binding table and path-local initialization.

  Binding collection and source-order checking are separate: a known local
  slot never implies that a declaration on another path has executed.
  """

  def __init__(
    self, scope: FunctionScope, signatures: dict[str, FunctionSignature], *,
    module_values: dict[str, ValueBinding] | None = None,
    imported_values: dict[str, ValueBinding] | None = None,
  ):
    self.scope = scope
    self.signatures = signatures
    self.local_names = set(scope.local_names)
    self.module_values = module_values or {}
    self.imported_values = imported_values or {}

  def require_initialized(self, name: str, span: SourceSpan, initialized: set[str]):
    """
    Resolve value names without treating a known module slot as an early value.

    Imported dependencies are ready before this module initializes. Owned slots
    must appear in the current path state; functions get the complete table and
    rely on runtime guards when invoked by an earlier initializer.
    """

    if name in self.imported_values:
      return

    if name not in self.local_names and name not in self.module_values:
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
    elif isinstance(expression, ModuleMember):
      name = f"{expression.namespace}.{expression.member}"
      if name not in self.imported_values:
        raise PyIndoError(f"Unknown module value: {name}", expression.span)
    elif isinstance(expression, (Unary, NonEmpty)):
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
    elif isinstance(expression, ComparisonChain):
      # Even a runtime-skipped link must have valid, initialized source operands.
      self.expression(expression.first, initialized)
      for link in expression.comparisons:
        self.expression(link.operand, initialized)
    elif isinstance(expression, Conditional):
      # Static diagnostics follow source order, including the unselected arm.
      self.expression(expression.true_value, initialized)
      self.expression(expression.condition, initialized)
      self.expression(expression.false_value, initialized)
    elif isinstance(expression, Call):
      if expression.callee != "tampilkan":
        signature = self.signatures.get(expression.callee)

        if signature is None:
          raise PyIndoError(f"Unknown function: {expression.callee}", expression.span)

        validate_call_arguments(expression, signature)
      elif expression.keywords:
        raise PyIndoError("'tampilkan' accepts positional arguments only", expression.keywords[0].span)

      for argument in expression.arguments:
        self.expression(argument, initialized)
      for keyword in expression.keywords:
        self.expression(keyword.value, initialized)
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

    name = (
      root.identifier if isinstance(root, Name) else
      f"{root.namespace}.{root.member}" if isinstance(root, ModuleMember) else None
    )
    binding = self.module_values.get(name) or self.imported_values.get(name)
    if name in self.scope.constant_names or (binding is not None and binding.is_constant):
      raise PyIndoError(f"Cannot mutate constant '{name}'", target.span)

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

      if statement.target in self.imported_values:
        raise PyIndoError(f"Cannot rebind imported value '{statement.target}'", statement.span)

      binding = self.module_values.get(statement.target)
      if statement.target in self.scope.constant_names or (binding is not None and binding.is_constant):
        raise PyIndoError(f"Cannot reassign constant '{statement.target}'", statement.span)

      self.expression(statement.value, initialized)
    elif isinstance(statement, Return):
      if statement.value is not None:
        self.expression(statement.value, initialized)
      elif not allows_none(self.scope.return_type):
        raise PyIndoError("Return value is required for this function", statement.span)

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
    elif isinstance(statement, Switch):
      return self.analyze_switch(statement, initialized, loop_depth=loop_depth)
    elif isinstance(statement, While):
      self.expression(statement.condition, initialized)
      self.block(statement.body, initialized, loop_depth=loop_depth + 1)
      # A possible zero-iteration path retains only incoming initialization.
      # This loop consumes its own break/continue exits, including nested ones.
    elif isinstance(statement, For):
      return self.analyze_for(statement, initialized, loop_depth=loop_depth)
    elif isinstance(statement, ForEach):
      # The iterable cannot read the as-yet uninitialized iteration binding.
      self.expression(statement.iterable, initialized)
      self.block(statement.body, initialized | {statement.name}, loop_depth=loop_depth + 1)
      # Even a nonempty literal does not establish initialization after the loop.
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
    return _join_branches(branches, initialized)

  def analyze_switch(self, statement: Switch, initialized: set[str], *, loop_depth: int) -> FlowResult:
    """
    Check all cases against incoming state without creating a new control target.

    Runtime laziness cannot hide invalid reads or stores. Only an explicit
    fallback removes the unmatched path, including when that fallback is empty.
    """

    self.expression(statement.subject, initialized)
    branches = []
    for case in statement.cases:
      for value in case.values:
        self.expression(value, initialized)
      branches.append(self.block(case.body, initialized, loop_depth=loop_depth))

    branches.append(
      FlowResult(set(initialized), True) if statement.else_body is None
      else self.block(statement.else_body, initialized, loop_depth=loop_depth)
    )
    return _join_branches(branches, initialized)

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


def _binding_type(annotation, span: SourceSpan) -> TypeSpec:
  """
  Require annotations even when an embedding caller constructs an AST directly.
  """

  if annotation is None:
    raise PyIndoError("Type annotation is required", span)
  return resolve_type(annotation)


def _analyze_program(
  program: Program, *, imported_signatures: dict[str, FunctionSignature] | None = None,
  namespace_names: set[str] | None = None, require_entrypoint: bool = True,
  imported_values: dict[str, ValueBinding] | None = None,
) -> ProgramSymbols:
  """
  Register functions/owned values, check initializers, then validate local paths.
  """

  signatures = dict(imported_signatures or {})
  namespaces = set(namespace_names or ())
  scopes = {}
  module_values = {}
  imported_values = dict(imported_values or {})

  for function in program.functions:
    if function.name in RESERVED_FUNCTION_NAMES or function.name in namespaces or function.name in imported_values:
      raise PyIndoError(
        f"Function name '{function.name}' is reserved", function.name_span or function.span,
      )

    if function.name in signatures:
      raise PyIndoError(f"Duplicate function: {function.name}", function.span)

    signatures[function.name] = FunctionSignature(
      function.name, [parameter.name for parameter in function.parameters], function.span,
      tuple(_binding_type(parameter.annotation, parameter.span) for parameter in function.parameters),
      _binding_type(function.return_annotation, function.span),
    )

  # Collect every owned binding before checking bodies; initializer order is
  # validated separately, while functions rely on runtime publication guards.
  for declaration in program.declarations:
    name = declaration.name
    if name in module_values:
      raise PyIndoError(f"Duplicate module declaration: {name}", declaration.span)
    if name in signatures or name in namespaces or name in imported_values or name in RESERVED_FUNCTION_NAMES | {"utama"}:
      raise PyIndoError(f"Module name '{name}' conflicts with an existing or reserved name", declaration.span)
    module_values[name] = ValueBinding(
      name, _binding_type(declaration.annotation, declaration.span), declaration.is_constant, declaration.span,
    )

  initializer_scope = FunctionScope("<module>", [], [], set())
  initializer_analyzer = FunctionAnalyzer(
    initializer_scope, signatures, module_values=module_values, imported_values=imported_values,
  )
  initialized_globals = set()
  for declaration in program.declarations:
    initializer_analyzer.expression(declaration.value, initialized_globals)
    initialized_globals.add(declaration.name)

  entry_function = next((function for function in program.functions if function.name == "utama"), None)
  if require_entrypoint and entry_function is None:
    raise PyIndoError("Entrypoint is not exist, you should create it first using `utama` function")

  if require_entrypoint:
    entry_signature = signatures["utama"]
    if len(entry_signature.parameters) not in (0, 2):
      raise PyIndoError("Entrypoint 'utama' requires zero or two parameters", entry_signature.span)

    if entry_signature.parameters:
      valid_arguments = (("himpunan", "campuran"), ("himpunan", "apapun"))
      if entry_signature.parameter_types[0] not in valid_arguments:
        raise PyIndoError(
          "Entrypoint argument list must be himpunan<campuran> or himpunan<apapun>",
          entry_function.parameters[0].annotation.span,
        )
      if entry_signature.parameter_types[1] != "desimal":
        raise PyIndoError("Entrypoint argument count must be desimal", entry_function.parameters[1].annotation.span)

  for function in program.functions:
    parameters = signatures[function.name].parameters
    local_names = []
    constant_names = set()
    binding_types = {}
    bindings = [
      (parameter.name, parameter.span, False, parameter.annotation) for parameter in function.parameters
    ]
    bindings.extend(
      (declaration.name, declaration.span, declaration.is_constant, declaration.annotation)
      for declaration in _declarations(function.body)
    )

    for name, span, is_constant, annotation in bindings:
      if name in signatures or name in namespaces or name == "tampilkan":
        raise PyIndoError(f"Local name '{name}' conflicts with a function", span)

      if name in module_values or name in imported_values:
        raise PyIndoError(f"Local name '{name}' conflicts with a module value", span)

      if name in local_names:
        raise PyIndoError(f"Duplicate local declaration: {name}", span)

      local_names.append(name)
      binding_types[name] = _binding_type(annotation, span)

      if is_constant:
        constant_names.add(name)

    scope = FunctionScope(
      function.name, parameters, local_names, constant_names,
      binding_types, signatures[function.name].return_type,
    )
    scopes[function.name] = scope
    flow = FunctionAnalyzer(
      scope, signatures, module_values=module_values, imported_values=imported_values,
    ).block(function.body, set(parameters) | set(module_values))
    if flow.falls_through and not allows_none(scope.return_type):
      raise PyIndoError("Function may finish without a return value", function.span)

  return ProgramSymbols(signatures, scopes, module_values, imported_values)


def analyze_program(
  program: Program, *, imported_signatures: dict[str, FunctionSignature] | None = None,
  namespace_names: set[str] | None = None, require_entrypoint: bool = True,
  imported_values: dict[str, ValueBinding] | None = None,
) -> ProgramSymbols:
  """
  Validate bindings and initialization, reporting the compiler's traversal limit.
  """

  try:
    return _analyze_program(
      program, imported_signatures=imported_signatures, namespace_names=namespace_names,
      require_entrypoint=require_entrypoint, imported_values=imported_values,
    )
  except RecursionError as complexity_error:
    raise PyIndoError(COMPLEXITY_ERROR_MESSAGE, program.span) from complexity_error
