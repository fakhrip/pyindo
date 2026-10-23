from dataclasses import dataclass, field
from types import CodeType

from bytecode import BinaryOp, Bytecode, Compare, CompilerFlags, Instr, Intrinsic1Op, Label
from bytecode.instr import InstrLocation

from pyindo.diagnostics import COMPLEXITY_ERROR_MESSAGE, SOURCE_NEWLINE_PATTERN, PyIndoError, SourceSpan
from pyindo.nodes import (
  Assignment, AugmentedAssignment, Binary, Break, Call, CallStatement, Conditional, Continue,
  Declaration, Delete, For, If, Index, IndexedAssignment, InterpolatedString,
  ListLiteral, Literal, Logical, Name, NonEmpty,
  Program, Return, Unary, While,
)
from pyindo.resolver import FunctionScope, FunctionSignature, analyze_program
from pyindo.types import TypeSpec


PREPARE_VALUE_NAME = "<pyindo:prepare_typed_value>"
PREPARE_CONSTANT_NAME = "<pyindo:prepare_typed_constant>"

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


@dataclass
class EmissionContext:
  scope: FunctionScope
  signatures: dict[str, FunctionSignature]
  source_text: str
  filename: str
  source_lines: list[str] = field(init=False)
  loop_targets: list[LoopTargets] = field(default_factory=list)

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


def emit_expression(expression, context: EmissionContext) -> list[Instr | Label]:
  """
  Emit an expression with exactly one result and no discarded intermediate values.
  """

  def instruction(name, argument=None, *, has_argument=True):
    return context.instruction(name, argument, span=expression.span, has_argument=has_argument)

  if isinstance(expression, Literal):
    return [instruction("LOAD_CONST", expression.value)]

  if isinstance(expression, Name):
    return [instruction("LOAD_FAST_CHECK", expression.identifier)]

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
      *emit_expression(expression.index, context),
      instruction("BINARY_OP", BinaryOp.SUBSCR),
    ]

  if isinstance(expression, NonEmpty):
    # Test the source operand once; later jumps only see this exact bool.
    return [*emit_expression(expression.operand, context), instruction("TO_BOOL", has_argument=False)]

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
    elif expression.operator == "in":
      instructions.append(instruction("CONTAINS_OP", 0))
    else:
      instructions.append(instruction("COMPARE_OP", COMPARISON_OPERATIONS[expression.operator]))

    return instructions

  if isinstance(expression, Call):
    callee = "print" if expression.callee == "tampilkan" else expression.callee
    # CPython 3.15 needs callable, NULL, then arguments in evaluation order.
    instructions = [instruction("LOAD_GLOBAL", (True, callee))]

    for argument in expression.arguments:
      instructions.extend(emit_expression(argument, context))

      if expression.callee == "tampilkan":
        instructions.append(instruction("FORMAT_SIMPLE", has_argument=False))

    if expression.callee == "tampilkan":
      # Printing is an expression too: leave its None result for the caller.
      instructions.extend([
        instruction("BUILD_STRING", len(expression.arguments)),
        instruction("LOAD_CONST", ""),
        instruction("LOAD_CONST", ("end",)),
        instruction("CALL_KW", 2),
      ])
    else:
      instructions.append(instruction("CALL", len(expression.arguments)))

    return instructions

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

  if not preserve_value and isinstance(expression, Conditional):
    false_label, end_label = Label(), Label()
    # Consumed predicates reuse known truth in selected logical arms. Value-
    # preserving contexts deliberately materialize and test the value again.
    return [
      *emit_truth_jump(
        expression.condition, context, when_true=False, target=false_label, preserve_value=False,
      ),
      *emit_truth_jump(
        expression.true_value, context, when_true=when_true, target=target, preserve_value=False,
      ),
      context.instruction("JUMP_FORWARD", end_label, span=expression.span), false_label,
      *emit_truth_jump(
        expression.false_value, context, when_true=when_true, target=target, preserve_value=False,
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


def _contract_context(kind: str, name: str, context: EmissionContext, span: SourceSpan) -> str:
  """
  Retain the source boundary in errors, including later mutations through aliases.
  """

  return f"{kind} '{name}' of '{context.scope.name}' on line {span.line}"


def emit_statement(statement, context: EmissionContext) -> list[Instr | Label]:
  """
  Emit a stack-neutral statement, or terminate the current frame with a return.
  """

  if isinstance(statement, (Declaration, Assignment)):
    name = statement.name if isinstance(statement, Declaration) else statement.target
    is_constant = isinstance(statement, Declaration) and statement.is_constant
    prepared = emit_type_guard(
      emit_expression(statement.value, context), context.scope.binding_types.get(name, "apapun"),
      _contract_context("binding", name, context, statement.span), context, statement.span,
      is_constant=is_constant,
    )
    return [
      *prepared,
      context.instruction("STORE_FAST", name, span=statement.span),
    ]

  if isinstance(statement, (IndexedAssignment, Delete)):
    target = statement.target
    # Assignment evaluates its RHS before resolving even a nested target base.
    instructions = (
      emit_expression(statement.value, context) if isinstance(statement, IndexedAssignment) else []
    )
    instructions.extend([
      *emit_expression(target.container, context),
      *emit_expression(target.index, context),
      context.instruction(
        "STORE_SUBSCR" if isinstance(statement, IndexedAssignment) else "DELETE_SUBSCR",
        span=target.span, has_argument=False,
      ),
    ])
    return instructions

  if isinstance(statement, AugmentedAssignment):
    # Read before the RHS and rebind; postfix syntax leaves no old/new value.
    computed = [
      context.instruction("LOAD_FAST_CHECK", statement.target, span=statement.span),
      *emit_expression(statement.value, context),
      context.instruction("BINARY_OP", BINARY_OPERATIONS[statement.operator], span=statement.span),
    ]
    return [
      *emit_type_guard(
        computed, context.scope.binding_types.get(statement.target, "apapun"),
        _contract_context("binding", statement.target, context, statement.span), context, statement.span,
      ),
      context.instruction("STORE_FAST", statement.target, span=statement.span),
    ]

  if isinstance(statement, (Break, Continue)):
    if not context.loop_targets:
      raise PyIndoError("Loop control requires an enclosing loop", statement.span)

    targets = context.loop_targets[-1]
    opcode = "JUMP_FORWARD" if isinstance(statement, Break) else targets.continue_opcode
    label = targets.break_label if isinstance(statement, Break) else targets.continue_label
    return [context.instruction(opcode, label, span=statement.span)]

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
    return [
      *emit_type_guard(
        instructions, context.scope.return_type,
        _contract_context("return", context.scope.name, context, statement.span), context, statement.span,
      ),
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


def compile_function(function, scope, *, signatures, source_text, filename) -> CodeType:
  """
  Assemble an optimized function frame with deterministic locals and metadata.
  """

  context = EmissionContext(scope, signatures, source_text, filename)
  instructions = [Instr("RESUME", 0, lineno=function.span.line)]

  # All caller arguments already exist before the first parameter is checked.
  for parameter in function.parameters:
    instructions.extend(emit_type_guard(
      [context.instruction("LOAD_FAST_CHECK", parameter.name, span=parameter.span)],
      scope.binding_types[parameter.name],
      _contract_context("parameter", parameter.name, context, parameter.span), context, parameter.span,
    ))
    instructions.append(context.instruction("STORE_FAST", parameter.name, span=parameter.span))

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


def compile_program(program: Program, *, filename: str = "<pyindo>") -> Bytecode:
  """
  Resolve a program and define every function before the guarded entrypoint call.
  """

  symbols = analyze_program(program)
  instructions = [Instr("RESUME", 0, lineno=1)]

  helpers = [("prepare_typed_value", PREPARE_VALUE_NAME)]
  if any(scope.constant_names for scope in symbols.scopes.values()):
    helpers.append(("prepare_typed_constant", PREPARE_CONSTANT_NAME))

  for helper_name, global_name in helpers:
    # An impossible source identifier avoids collisions and caller-side injection.
    instructions.extend([
      Instr("LOAD_CONST", 0, lineno=1),
      Instr("LOAD_CONST", (helper_name,), lineno=1),
      Instr("IMPORT_NAME", (False, False, "pyindo.type_checks"), lineno=1),
      Instr("IMPORT_FROM", helper_name, lineno=1),
      Instr("STORE_NAME", global_name, lineno=1),
      Instr("POP_TOP", lineno=1),
    ])

  for function in program.functions:
    try:
      function_code = compile_function(
        function, symbols.scopes[function.name], signatures=symbols.signatures,
        source_text=program.source_text, filename=filename,
      )
    except RecursionError as complexity_error:
      raise PyIndoError(COMPLEXITY_ERROR_MESSAGE, function.span) from complexity_error
    instructions.extend([
      Instr("LOAD_CONST", function_code, lineno=function.span.line),
      Instr("MAKE_FUNCTION"), Instr("STORE_NAME", function.name),
    ])

  module_exit = Label()
  instructions.extend([
    Instr("LOAD_NAME", "__name__"), Instr("LOAD_CONST", "__main__"),
    Instr("COMPARE_OP", Compare.EQ), Instr("TO_BOOL"),
    Instr("POP_JUMP_IF_FALSE", module_exit),
    Instr("LOAD_NAME", "utama"), Instr("PUSH_NULL"), Instr("CALL", 0),
    # A language return value never becomes the CLI's process exit status.
    Instr("POP_TOP"), module_exit,
    Instr("LOAD_CONST", None), Instr("RETURN_VALUE"),
  ])
  bytecode = Bytecode(instructions)
  bytecode.flags = CompilerFlags(0)
  bytecode.name = bytecode.qualname = "<module>"
  bytecode.filename = filename
  bytecode.first_lineno = 1

  return bytecode
