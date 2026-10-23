from dataclasses import dataclass, field
from types import CodeType

from bytecode import BinaryOp, Bytecode, Compare, CompilerFlags, Instr, Intrinsic1Op, Label
from bytecode.instr import InstrLocation

from pyindo.nodes import (
  Assignment, Binary, Call, CallStatement, Declaration, If, InterpolatedString,
  Literal, Name, Program, Return, Unary,
)
from pyindo.resolver import FunctionScope, FunctionSignature, analyze_program


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
class EmissionContext:
  scope: FunctionScope
  signatures: dict[str, FunctionSignature]
  source_text: str
  filename: str
  source_lines: list[str] = field(init=False)

  def __post_init__(self):
    self.source_lines = self.source_text.split("\n")

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
    else:
      instructions.append(instruction("UNARY_NEGATIVE", has_argument=False))

    return instructions

  if isinstance(expression, Binary):
    instructions = [
      *emit_expression(expression.left, context),
      *emit_expression(expression.right, context),
    ]

    if expression.operator in BINARY_OPERATIONS:
      instructions.append(instruction("BINARY_OP", BINARY_OPERATIONS[expression.operator]))
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


def emit_statement(statement, context: EmissionContext) -> list[Instr | Label]:
  """
  Emit a stack-neutral statement, or terminate the current frame with a return.
  """

  if isinstance(statement, (Declaration, Assignment)):
    name = statement.name if isinstance(statement, Declaration) else statement.target
    return [
      *emit_expression(statement.value, context),
      context.instruction("STORE_FAST", name, span=statement.span),
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
      instructions.extend(emit_expression(condition, context))
      instructions.extend([
        context.instruction("TO_BOOL", span=condition.span, has_argument=False),
        context.instruction("POP_JUMP_IF_FALSE", next_arm, span=condition.span),
      ])

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


def compile_function(function, scope, *, signatures, source_text, filename) -> CodeType:
  """
  Assemble an optimized function frame with deterministic locals and metadata.
  """

  context = EmissionContext(scope, signatures, source_text, filename)
  instructions = [Instr("RESUME", 0, lineno=function.span.line)]

  for statement in function.body:
    instructions.extend(emit_statement(statement, context))

  instructions.extend([Instr("LOAD_CONST", None), Instr("RETURN_VALUE")])
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

  for function in program.functions:
    function_code = compile_function(
      function, symbols.scopes[function.name], signatures=symbols.signatures,
      source_text=program.source_text, filename=filename,
    )
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
