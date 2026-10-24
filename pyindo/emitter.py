from dataclasses import dataclass, field
from types import CodeType

from bytecode import BinaryOp, Bytecode, Compare, CompilerFlags, Instr, Intrinsic1Op, Label
from bytecode.instr import InstrLocation

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, SOURCE_NEWLINE_PATTERN, PyIndoError, SourceSpan
from pyindo.nodes import (
  Assignment, AugmentedAssignment, Binary, Break, Call, CallStatement, ComparisonChain, Conditional, Continue,
  Declaration, Delete, Expression, For, ForEach, Function, If, Index, IndexedAssignment, InterpolatedString,
  ListLiteral, Literal, Logical, ModuleMember, Name, NonEmpty,
  Program, Return, SliceKey, Switch, Unary, While,
)
from pyindo.resolver import FunctionScope, FunctionSignature, ProgramSymbols, ValueBinding, analyze_program
from pyindo.runtime import MODULE_VALUE_NAMES
from pyindo.types import TypeSpec


PREPARE_VALUE_NAME = "<pyindo:prepare_typed_value>"
PREPARE_CONSTANT_NAME = "<pyindo:prepare_typed_constant>"
INVOKE_ENTRYPOINT_NAME = "<pyindo:invoke_entrypoint>"
ENTRYPOINT_RESULT_NAME = "<pyindo:entrypoint_result>"
LOAD_MODULE_IMPORTS_NAME = "<pyindo:load_module_imports>"
IMPORT_BINDINGS_NAME = "<pyindo:import_bindings>"
MODULE_EXPORT_NAME = "<pyindo:module_export>"
READ_MODULE_VALUE_NAME = "<pyindo:read_module_value>"
UNINITIALIZED_MODULE_VALUE_NAME = "<pyindo:module_uninitialized>"
MISSING_ARGUMENT_NAME = "<pyindo:missing_argument>"
MAKE_INCLUSIVE_SLICE_NAME = "<pyindo:make_inclusive_slice>"

BINARY_OPERATIONS = {
  "+": BinaryOp.ADD, "-": BinaryOp.SUBTRACT, "*": BinaryOp.MULTIPLY,
  "/": BinaryOp.TRUE_DIVIDE, "%": BinaryOp.REMAINDER, "**": BinaryOp.POWER,
  "&": BinaryOp.AND, "|": BinaryOp.OR, "<<": BinaryOp.LSHIFT, ">>": BinaryOp.RSHIFT,
}
COMPARISON_OPERATIONS = {
  "==": Compare.EQ, "!=": Compare.NE, "<": Compare.LT,
  "<=": Compare.LE, ">": Compare.GT, ">=": Compare.GE,
}


@dataclass
class LoopTargets:
  break_label: Label
  continue_label: Label
  continue_opcode: str
  is_iterator: bool = False


@dataclass
class EmissionContext:
  scope: FunctionScope
  signatures: dict[str, FunctionSignature]
  source_text: str
  filename: str
  source_lines: list[str] = field(init=False)
  loop_targets: list[LoopTargets] = field(default_factory=list)
  module_values: dict[str, ValueBinding] = field(default_factory=dict)
  imported_values: dict[str, ValueBinding] = field(default_factory=dict)

  def __post_init__(self):
    self.source_lines = SOURCE_NEWLINE_PATTERN.split(self.source_text)

  def instruction(self, name, argument=None, *, span, has_argument=True):
    """
    Convert Unicode character columns into CPython's zero-based UTF-8 columns.
    """

    location = InstrLocation(
      span.line, span.end_line,
      len(self.source_lines[span.line - 1][:span.column - 1].encode("utf-8")),
      len(self.source_lines[span.end_line - 1][:span.end_column - 1].encode("utf-8")),
    )

    if has_argument:
      return Instr(name, argument, location=location)

    return Instr(name, location=location)


def emit_comparison_operation(operator: str, context: EmissionContext, span: SourceSpan) -> Instr:
  """
  Consume two operands and leave their native comparison or membership result.
  """

  if operator in ("in", "not in"):
    return context.instruction("CONTAINS_OP", int(operator == "not in"), span=span)
  return context.instruction("COMPARE_OP", COMPARISON_OPERATIONS[operator], span=span)


def emit_comparison_chain(expression: ComparisonChain, context: EmissionContext) -> list[Instr | Label]:
  """
  Keep each middle operand once and return the selected original result object.

  Above any caller stack prefix, a nonfinal comparison leaves [right, result].
  Success retains right for the next link; failure drops right and keeps result.
  The final result is returned without a truth test, just like a raw comparison.
  """

  failed_label, end_label = Label(), Label()
  instructions = emit_expression(expression.first, context)
  for link in expression.comparisons[:-1]:
    instructions.extend([
      *emit_expression(link.operand, context),
      context.instruction("SWAP", 2, span=link.span),
      context.instruction("COPY", 2, span=link.span),
      emit_comparison_operation(link.operator, context, link.span),
      context.instruction("COPY", 1, span=link.span),
      context.instruction("TO_BOOL", span=link.span, has_argument=False),
      context.instruction("POP_JUMP_IF_FALSE", failed_label, span=link.span),
      context.instruction("POP_TOP", span=link.span, has_argument=False),
    ])

  final = expression.comparisons[-1]
  instructions.extend([
    *emit_expression(final.operand, context),
    emit_comparison_operation(final.operator, context, final.span),
    context.instruction("JUMP_FORWARD", end_label, span=expression.span), failed_label,
    context.instruction("SWAP", 2, span=expression.span),
    context.instruction("POP_TOP", span=expression.span, has_argument=False), end_label,
  ])
  return instructions


def emit_comparison_chain_truth_jump(
  expression: ComparisonChain, context: EmissionContext, *, when_true: bool, target: Label,
) -> list[Instr | Label]:
  """
  Consume a chain as a condition, testing every visited result exactly once.

  Early failure leaves only the retained middle operand above the caller's
  prefix. Discard it before routing known false; both exits restore that prefix.
  Preserving outer logic must materialize a raw chain instead of using this path.
  """

  failed_label, end_label = Label(), Label()
  instructions = emit_expression(expression.first, context)
  for link in expression.comparisons[:-1]:
    instructions.extend([
      *emit_expression(link.operand, context),
      context.instruction("SWAP", 2, span=link.span),
      context.instruction("COPY", 2, span=link.span),
      emit_comparison_operation(link.operator, context, link.span),
      context.instruction("TO_BOOL", span=link.span, has_argument=False),
      context.instruction("POP_JUMP_IF_FALSE", failed_label, span=link.span),
    ])

  final = expression.comparisons[-1]
  instructions.extend([
    *emit_expression(final.operand, context),
    emit_comparison_operation(final.operator, context, final.span),
    context.instruction("TO_BOOL", span=final.span, has_argument=False),
    context.instruction("POP_JUMP_IF_TRUE" if when_true else "POP_JUMP_IF_FALSE", target, span=final.span),
    context.instruction("JUMP_FORWARD", end_label, span=expression.span), failed_label,
    context.instruction("POP_TOP", span=expression.span, has_argument=False),
  ])
  if not when_true:
    instructions.append(context.instruction("JUMP_FORWARD", target, span=expression.span))
  instructions.append(end_label)
  return instructions


def emit_call(call: Call, context: EmissionContext) -> list[Instr | Label]:
  """
  Emit native argument binding while evaluating all supplied values in written order.

  Callable, NULL, positional values, named values and their name tuple sit above
  any caller prefix. CALL/CALL_KW consume them and leave exactly one result.
  """

  def instruction(name, argument=None, *, has_argument=True):
    return context.instruction(name, argument, span=call.span, has_argument=has_argument)

  callee = "print" if call.callee == "tampilkan" else call.callee
  if "." in callee:
    namespace, member = callee.split(".")
    # Preserve declared-export lookup, including descriptor-named functions.
    instructions = [
      instruction("LOAD_GLOBAL", (True, MODULE_EXPORT_NAME)),
      instruction("LOAD_GLOBAL", (False, namespace)),
      instruction("LOAD_CONST", member), instruction("CALL", 2),
      instruction("PUSH_NULL", has_argument=False),
    ]
  else:
    instructions = [instruction("LOAD_GLOBAL", (True, callee))]

  for argument in call.arguments:
    instructions.extend(emit_expression(argument, context))
    if call.callee == "tampilkan":
      instructions.append(instruction("FORMAT_SIMPLE", has_argument=False))

  if call.callee == "tampilkan":
    # Printing keeps its internal end option and positional-only source contract.
    instructions.extend([
      instruction("BUILD_STRING", len(call.arguments)), instruction("LOAD_CONST", ""),
      instruction("LOAD_CONST", ("end",)), instruction("CALL_KW", 2),
    ])
  elif call.keywords:
    for keyword in call.keywords:
      instructions.extend(emit_expression(keyword.value, context))
    instructions.extend([
      instruction("LOAD_CONST", tuple(keyword.name for keyword in call.keywords)),
      instruction("CALL_KW", len(call.arguments) + len(call.keywords)),
    ])
  else:
    instructions.append(instruction("CALL", len(call.arguments)))

  return instructions


def emit_subscript_key(key: Expression | SliceKey, context: EmissionContext) -> list[Instr | Label]:
  """
  Leave one index or inclusive slice key above the existing caller stack.

  Bounds evaluate before conversion. The shared helper call preserves the
  container and any pending RHS/iterator values for reads, writes and deletion.
  """

  if not isinstance(key, SliceKey):
    return emit_expression(key, context)

  return [
    context.instruction("LOAD_GLOBAL", (True, MAKE_INCLUSIVE_SLICE_NAME), span=key.span),
    *emit_expression(key.start, context),
    *emit_expression(key.stop, context),
    context.instruction("CALL", 2, span=key.span),
  ]


def emit_expression(expression, context: EmissionContext) -> list[Instr | Label]:
  """
  Emit an expression with exactly one result and no discarded intermediate values.
  """

  def instruction(name, argument=None, *, has_argument=True):
    return context.instruction(name, argument, span=expression.span, has_argument=has_argument)

  if isinstance(expression, Literal):
    return [instruction("LOAD_CONST", expression.value)]

  if isinstance(expression, Name):
    if expression.identifier in context.module_values or expression.identifier in context.imported_values:
      return emit_module_read(expression.identifier, context, expression.span)
    return [instruction("LOAD_FAST_CHECK", expression.identifier)]

  if isinstance(expression, ModuleMember):
    return [
      instruction("LOAD_GLOBAL", (True, MODULE_EXPORT_NAME)),
      instruction("LOAD_GLOBAL", (False, expression.namespace)),
      instruction("LOAD_CONST", expression.member),
      instruction("CALL", 2),
    ]

  if isinstance(expression, ListLiteral):
    instructions = []

    for item in expression.items:
      instructions.extend(emit_expression(item, context))

    # Build even empty lists at runtime; mutable instances never enter co_consts.
    instructions.append(instruction("BUILD_LIST", len(expression.items)))
    return instructions

  if isinstance(expression, Index):
    return [
      *emit_expression(expression.container, context),
      *emit_subscript_key(expression.index, context),
      instruction("BINARY_OP", BinaryOp.SUBSCR),
    ]

  if isinstance(expression, NonEmpty):
    # Test the source operand once; later jumps only see this exact bool.
    return [*emit_expression(expression.operand, context), instruction("TO_BOOL", has_argument=False)]

  if isinstance(expression, ComparisonChain):
    return emit_comparison_chain(expression, context)

  if isinstance(expression, InterpolatedString):
    instructions = []

    for part in expression.parts:
      if isinstance(part, str):
        instructions.append(instruction("LOAD_CONST", part))
      else:
        instructions.extend(emit_expression(part, context))
        instructions.append(instruction("FORMAT_SIMPLE", has_argument=False))

    # Text was decoded by the lexer; only expression results need formatting.
    instructions.append(instruction("BUILD_STRING", len(expression.parts)))
    return instructions

  if isinstance(expression, Unary):
    instructions = emit_expression(expression.operand, context)

    if expression.operator == "+":
      instructions.append(instruction("CALL_INTRINSIC_1", Intrinsic1Op.INTRINSIC_UNARY_POSITIVE))
    elif expression.operator == "not":
      instructions.extend([
        instruction("TO_BOOL", has_argument=False),
        instruction("UNARY_NOT", has_argument=False),
      ])
    else:
      instructions.append(instruction("UNARY_NEGATIVE", has_argument=False))

    return instructions

  if isinstance(expression, Logical):
    end_label = Label()

    # Reuse known truth across a chain; never test a selected operand twice.
    return [
      *emit_truth_jump(
        expression.left, context, when_true=expression.operator == "or", target=end_label,
      ),
      instruction("POP_TOP", has_argument=False),
      *emit_expression(expression.right, context), end_label,
    ]

  if isinstance(expression, Conditional):
    false_label, end_label = Label(), Label()
    # The condition runs first; both selected-arm exits leave exactly one value.
    return [
      *emit_truth_jump(
        expression.condition, context, when_true=False, target=false_label, preserve_value=False,
      ),
      *emit_expression(expression.true_value, context),
      instruction("JUMP_FORWARD", end_label), false_label,
      *emit_expression(expression.false_value, context), end_label,
    ]

  if isinstance(expression, Binary):
    instructions = [
      *emit_expression(expression.left, context),
      *emit_expression(expression.right, context),
    ]

    if expression.operator in BINARY_OPERATIONS:
      instructions.append(instruction("BINARY_OP", BINARY_OPERATIONS[expression.operator]))
    else:
      instructions.append(emit_comparison_operation(expression.operator, context, expression.span))

    return instructions

  if isinstance(expression, Call):
    return emit_call(expression, context)

  raise TypeError(f"Unknown expression node: {type(expression).__name__}")


def emit_truth_jump(
  expression, context: EmissionContext, *, when_true: bool, target: Label,
  preserve_value: bool = True,
) -> list[Instr | Label]:
  """
  Branch on truthiness, optionally retaining the selected original operand.

  A logical subtree routes its known truth directly to the enclosing decision.
  This avoids repeated __bool__ calls for both mixed and same-operator chains.
  Value expressions keep one operand on both exits; conditions consume it and
  leave the stack empty on both exits. Negated conditions reverse the decision.
  """

  if not preserve_value and isinstance(expression, Unary) and expression.operator == "not":
    return emit_truth_jump(
      expression.operand, context, when_true=not when_true, target=target, preserve_value=False,
    )

  if not preserve_value and isinstance(expression, ComparisonChain):
    return emit_comparison_chain_truth_jump(expression, context, when_true=when_true, target=target)

  if isinstance(expression, Conditional):
    false_label, end_label = Label(), Label()
    # CPython materializes the true arm before a value-preserving outer test.
    # The false arm can pass known truth through; consuming predicates can do
    # so for both arms. Keep this distinction observable to changing __bool__.
    emit_true_jump = _emit_value_truth_jump if preserve_value else emit_truth_jump
    return [
      *emit_truth_jump(
        expression.condition, context, when_true=False, target=false_label, preserve_value=False,
      ),
      *emit_true_jump(
        expression.true_value, context, when_true=when_true, target=target,
        preserve_value=preserve_value,
      ),
      context.instruction("JUMP_FORWARD", end_label, span=expression.span), false_label,
      *emit_truth_jump(
        expression.false_value, context, when_true=when_true, target=target,
        preserve_value=preserve_value,
      ), end_label,
    ]

  if isinstance(expression, Logical):
    short_circuit_on_true = expression.operator == "or"
    short_circuit_label = target if when_true == short_circuit_on_true else Label()
    instructions = emit_truth_jump(
      expression.left, context, when_true=short_circuit_on_true, target=short_circuit_label,
      preserve_value=preserve_value,
    )

    if preserve_value:
      instructions.append(context.instruction("POP_TOP", span=expression.span, has_argument=False))

    instructions.extend(emit_truth_jump(
      expression.right, context, when_true=when_true, target=target, preserve_value=preserve_value,
    ))

    if short_circuit_label is not target:
      instructions.append(short_circuit_label)

    return instructions

  return _emit_value_truth_jump(
    expression, context, when_true=when_true, target=target, preserve_value=preserve_value,
  )


def _emit_value_truth_jump(
  expression, context: EmissionContext, *, when_true: bool, target: Label,
  preserve_value: bool,
) -> list[Instr | Label]:
  """
  Evaluate a complete value, then test it with equal stack heights on both exits.
  """

  jump = "POP_JUMP_IF_TRUE" if when_true else "POP_JUMP_IF_FALSE"
  instructions = emit_expression(expression, context)

  if preserve_value:
    instructions.append(context.instruction("COPY", 1, span=expression.span))

  instructions.extend([
    context.instruction("TO_BOOL", span=expression.span, has_argument=False),
    context.instruction(jump, target, span=expression.span),
  ])
  return instructions


def emit_type_guard(
  value_instructions: list[Instr | Label], type_spec: TypeSpec,
  error_context: str, context: EmissionContext, span: SourceSpan, *,
  is_constant: bool = False,
) -> list[Instr | Label]:
  """
  Wrap a single evaluated result in a marshal-safe three-argument contract call.
  """

  helper = PREPARE_CONSTANT_NAME if is_constant else PREPARE_VALUE_NAME
  return [
    context.instruction("LOAD_GLOBAL", (True, helper), span=span),
    *value_instructions,
    context.instruction("LOAD_CONST", type_spec, span=span),
    context.instruction("LOAD_CONST", error_context, span=span),
    context.instruction("CALL", 3, span=span),
  ]


def emit_module_read(name: str, context: EmissionContext, span: SourceSpan) -> list[Instr | Label]:
  """
  Resolve a declared module value once, guarding its publication boundary.

  The seeded global always exists, preventing fallback to Python builtins.
  Imported references use the same guard boundary when live imports are wired.
  """

  return [
    context.instruction("LOAD_GLOBAL", (True, READ_MODULE_VALUE_NAME), span=span),
    context.instruction("LOAD_GLOBAL", (False, name), span=span),
    context.instruction("LOAD_CONST", name, span=span),
    context.instruction("CALL", 2, span=span),
  ]


def _contract_context(kind: str, name: str, context: EmissionContext, span: SourceSpan) -> str:
  """
  Retain the source boundary in errors, including later mutations through aliases.
  """

  return f"{kind} '{name}' of '{context.scope.name}' on line {span.line}"


def emit_switch(statement: Switch, context: EmissionContext) -> list[Instr | Label]:
  """
  Test ordered values against one captured subject, releasing it before bodies.

  Candidate evaluation preserves the stack prefix, including active iterator
  slots. Every body and normal exit has the pre-switch stack height, so existing
  break/continue/return cleanup needs no switch target or hidden local slot.
  """

  instructions = emit_expression(statement.subject, context)
  end_label = Label()

  for case in statement.cases:
    body_label, next_case_label = Label(), Label()
    for value in case.values:
      # Keep the original below a fresh copy: [prefix, subject, copy, value].
      # Rich comparison may return a foreign object; truth-test it exactly once.
      instructions.extend([
        context.instruction("COPY", 1, span=value.span),
        *emit_expression(value, context),
        context.instruction("COMPARE_OP", Compare.EQ, span=value.span),
        context.instruction("TO_BOOL", span=value.span, has_argument=False),
        context.instruction("POP_JUMP_IF_TRUE", body_label, span=value.span),
      ])

    instructions.extend([
      context.instruction("JUMP_FORWARD", next_case_label, span=case.span),
      body_label,
      context.instruction("POP_TOP", span=case.span, has_argument=False),
    ])
    for nested_statement in case.body:
      instructions.extend(emit_statement(nested_statement, context))
    instructions.extend([
      context.instruction("JUMP_FORWARD", end_label, span=case.span), next_case_label,
    ])

  # Failed candidates still leave the captured subject. Release it on both
  # fallback and no-match routes, including an explicitly empty fallback.
  instructions.append(context.instruction("POP_TOP", span=statement.span, has_argument=False))
  for nested_statement in statement.else_body or []:
    instructions.extend(emit_statement(nested_statement, context))
  instructions.append(end_label)
  return instructions


def emit_statement(statement, context: EmissionContext) -> list[Instr | Label]:
  """
  Emit a stack-neutral statement, or terminate the current frame with a return.
  """

  if isinstance(statement, Switch):
    return emit_switch(statement, context)

  if isinstance(statement, (Declaration, Assignment)):
    name = statement.name if isinstance(statement, Declaration) else statement.target
    is_constant = isinstance(statement, Declaration) and statement.is_constant
    binding = context.module_values.get(name)
    instructions = []
    if binding is not None and isinstance(statement, Assignment):
      # A function cannot publish a later declaration by rebinding it early.
      instructions.extend(emit_module_read(name, context, statement.span))
      instructions.append(context.instruction("POP_TOP", span=statement.span, has_argument=False))
    prepared = emit_type_guard(
      emit_expression(statement.value, context),
      binding.type_spec if binding is not None else context.scope.binding_types.get(name, "apapun"),
      _contract_context("binding", name, context, statement.span), context, statement.span,
      is_constant=is_constant,
    )
    return [
      *instructions, *prepared,
      context.instruction("STORE_GLOBAL" if binding is not None else "STORE_FAST", name, span=statement.span),
    ]

  if isinstance(statement, (IndexedAssignment, Delete)):
    target = statement.target
    # Assignment evaluates its RHS before resolving even a nested target base.
    instructions = (
      emit_expression(statement.value, context) if isinstance(statement, IndexedAssignment) else []
    )
    instructions.extend([
      *emit_expression(target.container, context),
      *emit_subscript_key(target.index, context),
      context.instruction(
        "STORE_SUBSCR" if isinstance(statement, IndexedAssignment) else "DELETE_SUBSCR",
        span=target.span, has_argument=False,
      ),
    ])
    return instructions

  if isinstance(statement, AugmentedAssignment):
    # Read before the RHS and rebind; postfix syntax leaves no old/new value.
    binding = context.module_values.get(statement.target)
    computed = [
      *(
        emit_module_read(statement.target, context, statement.span) if binding is not None else
        [context.instruction("LOAD_FAST_CHECK", statement.target, span=statement.span)]
      ),
      *emit_expression(statement.value, context),
      context.instruction("BINARY_OP", BINARY_OPERATIONS[statement.operator], span=statement.span),
    ]
    return [
      *emit_type_guard(
        computed, binding.type_spec if binding is not None else context.scope.binding_types.get(statement.target, "apapun"),
        _contract_context("binding", statement.target, context, statement.span), context, statement.span,
      ),
      context.instruction("STORE_GLOBAL" if binding is not None else "STORE_FAST", statement.target, span=statement.span),
    ]

  if isinstance(statement, (Break, Continue)):
    if not context.loop_targets:
      raise PyIndoError("Loop control requires an enclosing loop", statement.span)

    targets = context.loop_targets[-1]
    opcode = "JUMP_FORWARD" if isinstance(statement, Break) else targets.continue_opcode
    label = targets.break_label if isinstance(statement, Break) else targets.continue_label
    instructions = []

    if isinstance(statement, Break) and targets.is_iterator:
      # Only this loop exits; retain any enclosing iterator's two stack slots.
      instructions.extend([
        context.instruction("POP_TOP", span=statement.span, has_argument=False),
        context.instruction("POP_TOP", span=statement.span, has_argument=False),
      ])

    return [*instructions, context.instruction(opcode, label, span=statement.span)]

  if isinstance(statement, While):
    condition_label, exit_label = Label(), Label()
    return [
      condition_label,
      *emit_truth_jump(
        statement.condition, context, when_true=False, target=exit_label, preserve_value=False,
      ),
      *emit_loop_body(
        statement.body, context, LoopTargets(exit_label, condition_label, "JUMP_BACKWARD"),
      ),
      context.instruction("JUMP_BACKWARD", condition_label, span=statement.span), exit_label,
    ]

  if isinstance(statement, For):
    condition_label, update_label, exit_label = Label(), Label(), Label()
    instructions = (
      emit_statement(statement.initializer, context) if statement.initializer is not None else []
    )
    instructions.append(condition_label)

    if statement.condition is not None:
      instructions.extend(emit_truth_jump(
        statement.condition, context, when_true=False, target=exit_label, preserve_value=False,
      ))

    instructions.extend(emit_loop_body(
      statement.body, context, LoopTargets(exit_label, update_label, "JUMP_FORWARD"),
    ))
    # Continue reaches this update exactly once; break and return skip it.
    instructions.append(update_label)

    if statement.update is not None:
      instructions.extend(emit_statement(statement.update, context))

    instructions.extend([
      context.instruction("JUMP_BACKWARD", condition_label, span=statement.span), exit_label,
    ])
    return instructions

  if isinstance(statement, ForEach):
    next_label, exhausted_label, exit_label = Label(), Label(), Label()
    # CPython 3.15 retains iterator + index_or_null below each yielded item.
    # Move the item above helper/NULL before guarding it, without hidden locals.
    item = emit_type_guard(
      [
        context.instruction("SWAP", 2, span=statement.binding_span),
        context.instruction("SWAP", 3, span=statement.binding_span),
      ], context.scope.binding_types[statement.name],
      _contract_context("binding", statement.name, context, statement.binding_span),
      context, statement.binding_span, is_constant=statement.is_constant,
    )
    return [
      *emit_expression(statement.iterable, context),
      context.instruction("GET_ITER", 0, span=statement.iterable.span), next_label,
      context.instruction("FOR_ITER", exhausted_label, span=statement.iterable.span),
      *item, context.instruction("STORE_FAST", statement.name, span=statement.binding_span),
      *emit_loop_body(
        statement.body, context, LoopTargets(exit_label, next_label, "JUMP_BACKWARD", True),
      ),
      context.instruction("JUMP_BACKWARD", next_label, span=statement.span), exhausted_label,
      # Keep this native exhaustion pair together; break skips it after cleanup.
      context.instruction("END_FOR", span=statement.span, has_argument=False),
      context.instruction("POP_ITER", span=statement.span, has_argument=False), exit_label,
    ]

  if isinstance(statement, CallStatement):
    return [
      *emit_expression(statement.call, context),
      context.instruction("POP_TOP", span=statement.span, has_argument=False),
    ]

  if isinstance(statement, Return):
    instructions = (
      emit_expression(statement.value, context) if statement.value is not None
      else [context.instruction("LOAD_CONST", None, span=statement.span)]
    )
    instructions = emit_type_guard(
      instructions, context.scope.return_type,
      _contract_context("return", context.scope.name, context, statement.span), context, statement.span,
    )

    for targets in reversed(context.loop_targets):
      if targets.is_iterator:
        # Preserve the guarded result while releasing each enclosing iterator.
        instructions.extend([
          context.instruction("SWAP", 3, span=statement.span),
          context.instruction("POP_TOP", span=statement.span, has_argument=False),
          context.instruction("POP_TOP", span=statement.span, has_argument=False),
        ])

    return [
      *instructions,
      context.instruction("RETURN_VALUE", span=statement.span, has_argument=False),
    ]

  if isinstance(statement, If):
    instructions = []
    end_label = Label()

    for condition, body in statement.branches:
      # These destinations belong to this chain, never to a nested condition.
      next_arm = Label()
      instructions.extend(emit_truth_jump(
        condition, context, when_true=False, target=next_arm, preserve_value=False,
      ))

      for nested_statement in body:
        instructions.extend(emit_statement(nested_statement, context))

      instructions.extend([
        context.instruction("JUMP_FORWARD", end_label, span=statement.span), next_arm,
      ])

    for nested_statement in statement.else_body or []:
      instructions.extend(emit_statement(nested_statement, context))

    instructions.append(end_label)
    return instructions

  raise TypeError(f"Unknown statement node: {type(statement).__name__}")


def emit_loop_body(body, context: EmissionContext, targets: LoopTargets) -> list[Instr | Label]:
  """
  Emit a stack-neutral body with targets owned by this loop alone.

  Always restore the enclosing target stack, including when nested emission
  fails. Each function has a fresh context and cannot inherit caller targets.
  """

  instructions = []
  context.loop_targets.append(targets)

  try:
    for statement in body:
      instructions.extend(emit_statement(statement, context))
  finally:
    context.loop_targets.pop()

  return instructions


def emit_parameter_bindings(function: Function, context: EmissionContext) -> list[Instr | Label]:
  """
  Evaluate omitted defaults and check each parameter in declaration order.

  Native binding has already evaluated and assigned all supplied arguments.
  Store each checked value before the next default reads an earlier parameter.
  """

  instructions = []
  for parameter in function.parameters:
    if parameter.default is not None:
      supplied_label = Label()
      instructions.extend([
        context.instruction("LOAD_FAST_CHECK", parameter.name, span=parameter.span),
        context.instruction("LOAD_GLOBAL", (False, MISSING_ARGUMENT_NAME), span=parameter.span),
        context.instruction("IS_OP", 0, span=parameter.span),
        context.instruction("POP_JUMP_IF_FALSE", supplied_label, span=parameter.span),
        *emit_expression(parameter.default, context),
        context.instruction("STORE_FAST", parameter.name, span=parameter.span), supplied_label,
      ])

    instructions.extend(emit_type_guard(
      [context.instruction("LOAD_FAST_CHECK", parameter.name, span=parameter.span)],
      context.scope.binding_types[parameter.name],
      _contract_context("parameter", parameter.name, context, parameter.span), context, parameter.span,
    ))
    instructions.append(context.instruction("STORE_FAST", parameter.name, span=parameter.span))

  return instructions


def compile_function(
  function, scope, *, signatures, source_text, filename,
  module_values=None, imported_values=None,
) -> CodeType:
  """
  Assemble an optimized function frame with deterministic locals and metadata.
  """

  context = EmissionContext(
    scope, signatures, source_text, filename,
    module_values=module_values or {}, imported_values=imported_values or {},
  )
  instructions = [Instr("RESUME", 0, lineno=function.span.line)]

  instructions.extend(emit_parameter_bindings(function, context))

  for statement in function.body:
    instructions.extend(emit_statement(statement, context))

  instructions.extend(emit_type_guard(
    [context.instruction("LOAD_CONST", None, span=function.span)], scope.return_type,
    _contract_context("return", function.name, context, function.span), context, function.span,
  ))
  instructions.append(context.instruction("RETURN_VALUE", span=function.span, has_argument=False))
  bytecode = Bytecode(instructions)
  bytecode.flags = CompilerFlags.OPTIMIZED | CompilerFlags.NEWLOCALS
  bytecode.argcount = len(scope.parameters)
  bytecode.posonlyargcount = 0
  bytecode.kwonlyargcount = 0
  # The assembler seeds all slots here, including unused/unreachable locals.
  bytecode.argnames = list(scope.local_names)
  bytecode.name = bytecode.qualname = function.name
  bytecode.filename = filename
  bytecode.first_lineno = function.span.line

  return bytecode.to_code()


def compile_program(
  program: Program, *, filename: str = "<pyindo>", symbols: ProgramSymbols | None = None,
  is_library: bool = False, module_bundle: tuple = (), import_bindings: tuple = (),
) -> Bytecode:
  """
  Define functions, publish ordered module state, then invoke the root entrypoint.

  Seeding owned globals precedes dependency initialization so re-execution never
  exposes an old value. Imports and functions are available to all initializers.
  """

  if symbols is None:
    if program.imports:
      raise PyIndoError("Imports require module resolution", program.imports[0].span)
    symbols = analyze_program(program, require_entrypoint=not is_library)
  instructions = [
    Instr("RESUME", 0, lineno=1),
    # Clear a previous main result even when this execution only imports definitions.
    Instr("LOAD_CONST", None, lineno=1), Instr("STORE_NAME", ENTRYPOINT_RESULT_NAME, lineno=1),
  ]

  helpers = [
    ("pyindo.type_checks", "prepare_typed_value", PREPARE_VALUE_NAME),
    ("pyindo.runtime", "invoke_entrypoint", INVOKE_ENTRYPOINT_NAME),
    ("pyindo.runtime", "make_inclusive_slice", MAKE_INCLUSIVE_SLICE_NAME),
  ]
  if any(scope.constant_names for scope in symbols.scopes.values()) or any(
    binding.is_constant for binding in symbols.module_values.values()
  ):
    helpers.append(("pyindo.type_checks", "prepare_typed_constant", PREPARE_CONSTANT_NAME))
  if import_bindings:
    helpers.append(("pyindo.runtime", "load_module_imports", LOAD_MODULE_IMPORTS_NAME))
  if any("." in name for name in symbols.signatures) or any("." in name for name in symbols.imported_values):
    helpers.append(("pyindo.runtime", "module_export", MODULE_EXPORT_NAME))
  if symbols.module_values or symbols.imported_values:
    helpers.append(("pyindo.runtime", "read_module_value", READ_MODULE_VALUE_NAME))
  if symbols.module_values:
    helpers.append(("pyindo.runtime", "_UNINITIALIZED_MODULE_VALUE", UNINITIALIZED_MODULE_VALUE_NAME))
  if any(symbols.signatures[function.name].default_count for function in program.functions):
    helpers.append(("pyindo.runtime", "_MISSING_ARGUMENT", MISSING_ARGUMENT_NAME))

  for module_name, helper_name, global_name in helpers:
    # An impossible source identifier avoids collisions and caller-side injection.
    instructions.extend([
      Instr("LOAD_CONST", 0, lineno=1),
      Instr("LOAD_CONST", (helper_name,), lineno=1),
      Instr("IMPORT_NAME", (False, False, module_name), lineno=1),
      Instr("IMPORT_FROM", helper_name, lineno=1),
      Instr("STORE_NAME", global_name, lineno=1),
      Instr("POP_TOP", lineno=1),
    ])

  # Private metadata classifies named value imports without changing bundle
  # triples. Real values/markers are created at execution, never in co_consts.
  instructions.extend([
    Instr("LOAD_CONST", tuple(symbols.module_values)), Instr("STORE_NAME", MODULE_VALUE_NAMES),
  ])
  for name in symbols.module_values:
    instructions.extend([
      Instr("LOAD_NAME", UNINITIALIZED_MODULE_VALUE_NAME), Instr("STORE_NAME", name),
    ])

  if import_bindings:
    # Tuple nesting preserves library filenames during legacy root-only rewrites.
    instructions.extend([
      Instr("LOAD_NAME", LOAD_MODULE_IMPORTS_NAME), Instr("PUSH_NULL"),
      Instr("LOAD_CONST", module_bundle), Instr("LOAD_CONST", import_bindings),
      Instr("CALL", 2), Instr("STORE_NAME", IMPORT_BINDINGS_NAME),
    ])
    for alias, _, _ in import_bindings:
      instructions.extend([
        Instr("LOAD_NAME", IMPORT_BINDINGS_NAME), Instr("LOAD_CONST", alias),
        Instr("BINARY_OP", BinaryOp.SUBSCR), Instr("STORE_NAME", alias),
      ])
    instructions.append(Instr("DELETE_NAME", IMPORT_BINDINGS_NAME))

  for function in program.functions:
    try:
      function_code = compile_function(
        function, symbols.scopes[function.name], signatures=symbols.signatures,
        source_text=program.source_text, filename=filename,
        module_values=symbols.module_values, imported_values=symbols.imported_values,
      )
    except RecursionError as complexity_error:
      raise PyIndoError(COMPLEXITY_ERROR_MESSAGE, function.span) from complexity_error
    default_count = symbols.signatures[function.name].default_count
    if default_count:
      # Only markers become native defaults. Source expressions run in the
      # callee; runtime imports keep marker objects out of marshaled constants.
      instructions.extend(Instr("LOAD_NAME", MISSING_ARGUMENT_NAME) for _ in range(default_count))
      instructions.append(Instr("BUILD_TUPLE", default_count))
    instructions.extend([
      Instr("LOAD_CONST", function_code, lineno=function.span.line),
      Instr("MAKE_FUNCTION"),
    ])
    if default_count:
      instructions.append(Instr("SET_FUNCTION_ATTRIBUTE", 1))
    instructions.append(Instr("STORE_NAME", function.name))

  initializer_context = EmissionContext(
    FunctionScope("<module>", [], [], set()), symbols.signatures, program.source_text, filename,
    module_values=symbols.module_values, imported_values=symbols.imported_values,
  )
  for declaration in program.declarations:
    try:
      instructions.extend(emit_statement(declaration, initializer_context))
    except RecursionError as complexity_error:
      raise PyIndoError(COMPLEXITY_ERROR_MESSAGE, declaration.span) from complexity_error

  if not is_library:
    module_exit = Label()
    instructions.extend([
      Instr("LOAD_NAME", "__name__"), Instr("LOAD_CONST", "__main__"),
      Instr("COMPARE_OP", Compare.EQ), Instr("TO_BOOL"),
      Instr("POP_JUMP_IF_FALSE", module_exit),
      Instr("LOAD_NAME", INVOKE_ENTRYPOINT_NAME), Instr("PUSH_NULL"),
      Instr("LOAD_NAME", "utama"), Instr("LOAD_CONST", len(symbols.signatures["utama"].parameters)),
      Instr("CALL", 2),
      # Record the raw return; only the CLI interprets process status.
      Instr("STORE_NAME", ENTRYPOINT_RESULT_NAME), module_exit,
    ])
  instructions.extend([Instr("LOAD_CONST", None), Instr("RETURN_VALUE")])
  bytecode = Bytecode(instructions)
  bytecode.flags = CompilerFlags(0)
  bytecode.name = bytecode.qualname = "<module>"
  bytecode.filename = filename
  bytecode.first_lineno = 1

  return bytecode
