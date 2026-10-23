from types import CodeType
from typing import Tuple, Union
from bytecode import BinaryOp, Compare, Instr, Bytecode, Label

from pyindo.types import LiteralString
from pyindo.runtime import ensure_supported_runtime

import re
import codecs

from pyindo.emitter import compile_program


def compile_source(source_text: str, *, filename: str = "<pyindo>") -> CodeType:
  """
  Compile source through syntax, semantic analysis, and the CPython 3.15 emitter.

  Check the target runtime before parsing or assembling; user-facing errors
  remain structured until the CLI or legacy parser facade renders them.
  """

  ensure_supported_runtime()

  from pyindo.syntax import parse_module

  return compile_program(parse_module(source_text), filename=filename).to_code()


def decode_escapes(s):
    ESCAPE_SEQUENCE_RE = re.compile(
        r"""
        ( \\U........      # 8-digit hex escapes
        | \\u....          # 4-digit hex escapes
        | \\x..            # 2-digit hex escapes
        | \\[0-7]{1,3}     # Octal escapes
        | \\N\{[^}]+\}     # Unicode characters by name
        | \\[\\'"abfnrtv]  # Single-character escapes
        )""",
        re.UNICODE | re.VERBOSE,
    )

    def decode_match(match):
        return codecs.decode(match.group(0), "unicode-escape")

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)


def load_const_or_name(data: tuple or str) -> Instr:
    if isinstance(data, tuple):
        match data:
            case (v_value, v_type) if v_type == int:
                return Instr("LOAD_CONST", int(v_value))
            case (v_value, v_type) if v_type == float:
                return Instr("LOAD_CONST", float(v_value))
            case (v_value, v_type) if v_type == str:
                return Instr("LOAD_CONST", str(v_value))
            case (v_value, v_type) if v_type == bool:
                if v_value in ["benar", "BENAR"]:
                    return Instr("LOAD_CONST", True)
                elif v_value in ["salah", "SALAH"]:
                    return Instr("LOAD_CONST", False)
                else:
                    print("TODO: Compiler error")
    elif isinstance(data, str):
        return Instr("LOAD_NAME", data)
    else:
        print("TODO: Compiler error")


def bool_operation(
    l_operand: tuple or list or str, r_operand: tuple or str or None, o_type: str
) -> list:
    bytecodes = []

    if isinstance(l_operand, tuple) or isinstance(l_operand, str):
        bytecodes.append(load_const_or_name(l_operand))
    else:
        bytecodes.extend(l_operand)

    if r_operand:
        bytecodes.append(load_const_or_name(r_operand))

    match o_type:
        case "&&":
            print("TODO: Implement the && bool operation")
        case "||":
            print("TODO: Implement the || bool operation")

    return bytecodes


def math_operation(
  l_operand: tuple | list | str,
  r_operand: tuple | str | None,
  o_type: str,
) -> list:
  """
  Load both operands and emit one CPython 3.15 binary operation.

  Operands may be typed literals, names, or already emitted instructions.
  Return the instructions with the expression result left on the stack.
  """

  bytecodes = []

  for operand in (l_operand, r_operand):
    if operand is None:
      continue

    if isinstance(operand, (tuple, str)):
      bytecodes.append(load_const_or_name(operand))
    else:
      bytecodes.extend(operand)

  operation_by_symbol = {
    "+": BinaryOp.ADD,
    "-": BinaryOp.SUBTRACT,
    "/": BinaryOp.TRUE_DIVIDE,
    "*": BinaryOp.MULTIPLY,
    "&": BinaryOp.AND,
    "%": BinaryOp.REMAINDER,
    "|": BinaryOp.OR,
    "<<": BinaryOp.LSHIFT,
    ">>": BinaryOp.RSHIFT,
    "**": BinaryOp.POWER,
  }

  # BINARY_OP consumes left/right operands and leaves one result.
  bytecodes.append(Instr("BINARY_OP", operation_by_symbol[o_type]))

  return bytecodes


def comparison(
    l_operand: tuple or list or str, r_operand: tuple or str or None, c_type: str
) -> list:
    bytecodes = []

    if isinstance(l_operand, tuple) or isinstance(l_operand, str):
        bytecodes.append(load_const_or_name(l_operand))
    else:
        bytecodes.extend(l_operand)

    if r_operand:
        bytecodes.append(load_const_or_name(r_operand))

    match c_type:
        case "==":
            bytecodes.append(Instr("COMPARE_OP", Compare.EQ))
        case "!=":
            bytecodes.append(Instr("COMPARE_OP", Compare.NE))
        case ">":
            bytecodes.append(Instr("COMPARE_OP", Compare.GT))
        case "<":
            bytecodes.append(Instr("COMPARE_OP", Compare.LT))
        case ">=":
            bytecodes.append(Instr("COMPARE_OP", Compare.GE))
        case "<=":
            bytecodes.append(Instr("COMPARE_OP", Compare.LE))

    return bytecodes


def condition(
  expressions: list,
  statements: list,
  other_statements: list,
  c_type: str,
  jump_label: Union[Label, None],
  condition_label: Union[Label, None],
) -> list:
  """
  Emit a braced if/else branch using abstract destination labels.

  Convert condition results to exact Booleans before a conditional jump;
  CPython 3.15 does not accept arbitrary truthy objects at that boundary.
  """

  bytecodes = []

  match c_type:
    case "selainnya":
      bytecodes.extend(statements)

    case "selainnya jika" | "jika":
      bytecodes.extend(expressions)

      if condition_label is not None:
        bytecodes.extend([
          Instr("TO_BOOL"),
          Instr("POP_JUMP_IF_FALSE", condition_label),
        ])

      bytecodes.extend(statements)

      # A taken branch skips the remaining alternatives in the same chain.
      if jump_label is not None:
        bytecodes.append(Instr("JUMP_FORWARD", jump_label))

      bytecodes.extend(other_statements)

  return bytecodes


def format_print(args: list, line_number: int, is_global_scope: bool) -> list:
  """
  Build one output string and call print with an empty end argument.

  Literal text and interpolation instructions retain their source order.
  Discard print's result so subsequent statements start with a clean stack.
  """

  bytecodes = []

  # CPython 3.15 calls expect the callable followed by NULL, then arguments.
  # LOAD_GLOBAL can push both entries; LOAD_NAME needs an explicit NULL.
  if is_global_scope:
    bytecodes.extend([
      Instr("LOAD_NAME", "print", lineno=line_number),
      Instr("PUSH_NULL"),
    ])
  else:
    bytecodes.append(Instr("LOAD_GLOBAL", (True, "print"), lineno=line_number))

  string_part_count = 0

  for argument in args:
    match argument:
      case (literal_value, literal_type) if literal_type == LiteralString:
        bytecodes.append(Instr("LOAD_CONST", decode_escapes(literal_value)))
        string_part_count += 1

      case list(_) as expression_bytecodes if expression_bytecodes:
        bytecodes.extend(expression_bytecodes)
        bytecodes.append(Instr("FORMAT_SIMPLE"))
        string_part_count += 1

  # Join the pieces, pass end="" as a keyword, and discard the None result.
  bytecodes.extend([
    Instr("BUILD_STRING", string_part_count),
    Instr("LOAD_CONST", ""),
    Instr("LOAD_CONST", ("end",)),
    Instr("CALL_KW", 2),
    Instr("POP_TOP"),
  ])

  return bytecodes


def call_function(
  function_name: str, function_params: list, line_number: int, is_global_scope: bool
) -> list:
  """
  Emit a statement call, delegating tampilkan to the formatting helper.

  User functions currently take no arguments. Discard only the call's
  result; the enclosing function or module must continue to its next statement.
  """

  if function_name == "tampilkan":
    return format_print(function_params, line_number, is_global_scope)

  if function_params:
    raise ValueError("User-function arguments are not supported yet")

  bytecodes = []

  # Both loading paths leave callable, NULL on the stack in that order.
  if is_global_scope:
    bytecodes.extend([
      Instr("LOAD_NAME", function_name, lineno=line_number),
      Instr("PUSH_NULL"),
    ])
  else:
    bytecodes.append(Instr("LOAD_GLOBAL", (True, function_name), lineno=line_number))

  bytecodes.extend([
    Instr("CALL", 0),
    Instr("POP_TOP"),
  ])

  return bytecodes


def define_function_content(
  function_name: str,
  function_bytecodes: dict,
  is_entrypoint_function: bool,
  line_number: int,
) -> Tuple[list, CodeType | None]:
  """
  Assemble a function body and return its definition instructions/code object.

  utama remains inline under the module's __main__ guard for this milestone.
  Other named functions receive a separate code object and their own return.
  """

  bytecodes = []
  function_codechunk = None

  if is_entrypoint_function:
    tail_bytecodes, module_exit_label = function_bytecodes["tail"]

    # The guard consumes its Boolean and skips the inline entrypoint when
    # code is inspected under a namespace other than __main__.
    bytecodes.extend([
      *function_bytecodes["header"],
      Instr("TO_BOOL"),
      Instr("POP_JUMP_IF_FALSE", module_exit_label),
      *function_bytecodes["content"],
      *tail_bytecodes,
    ])
  elif function_name:
    compiled_bytecode = compile_bytecodes(
      [*function_bytecodes["content"], *function_bytecodes["tail"][0]],
      name=function_name,
    )
    function_codechunk = compiled_bytecode.to_code()

    # MAKE_FUNCTION now consumes only the code object. An old qualname
    # constant or flag operand would corrupt the definition's stack layout.
    bytecodes.extend([
      *function_bytecodes["header"],
      Instr("LOAD_CONST", function_codechunk, lineno=line_number),
      Instr("MAKE_FUNCTION"),
      Instr("STORE_NAME", function_name),
    ])
  else:
    # Preserve the parser's existing inline anonymous-block representation.
    bytecodes.extend([
      *function_bytecodes["header"],
      *function_bytecodes["content"],
    ])

  return (bytecodes, function_codechunk)


def define_function_tail(is_entrypoint_function: bool) -> Tuple[list, Label]:
    if is_entrypoint_function:
        label_else = Label()
        return (
            [
                label_else,
                Instr("LOAD_CONST", None),
                Instr("RETURN_VALUE"),
            ],
            label_else,
        )

    return (
        [
            Instr("LOAD_CONST", None),  # TODO: Add function return value
            Instr("RETURN_VALUE"),
        ],
    )


def define_function_wrapper(
    function_name: str,
    function_params: list,
    is_entrypoint_function: bool,
    line_number: int,
) -> Tuple[list, Tuple]:
    bytecodes = []

    if is_entrypoint_function:
        # Function header definition for entrypoint
        bytecodes.extend(
            [
                Instr("LOAD_NAME", "__name__", lineno=line_number),
                Instr("LOAD_CONST", "__main__"),
                Instr("COMPARE_OP", Compare.EQ),
            ]
        )

        # Also define the function tail for entrypoint
        return (bytecodes, define_function_tail(is_entrypoint_function))
    else:
        # Function header definition for other functions
        for param in function_params:
            bytecodes.extend(
                [
                    Instr("LOAD_CONST", param["name"], lineno=line_number),
                    Instr("LOAD_NAME", param["type"], lineno=line_number),
                ]
            )

        if len(function_params) > 0:
            bytecodes.append(Instr("BUILD_TUPLE", 2 * len(function_params)))

    return (bytecodes, define_function_tail(is_entrypoint_function))


def _set_code_filename(code: CodeType, filename: str) -> CodeType:
  """
  Propagate source identity through nested code constants for diagnostics.

  replace() changes only metadata and nested constants; the assembler still
  owns all bytecode encoding, jump resolution, and stack calculations.
  """

  constants = tuple(
    _set_code_filename(value, filename) if isinstance(value, CodeType) else value
    for value in code.co_consts
  )

  return code.replace(co_filename=filename, co_consts=constants)


def compile_bytecodes(
  bytecodes: list,
  *,
  filename: str = "<pyindo>",
  name: str = "<module>",
) -> Bytecode:
  """
  Assemble abstract instructions with source metadata and a valid fallthrough.

  Return a Bytecode object; to_code() resolves labels, inline caches, and
  stack size. Reject other runtimes before assembling version-specific code.
  """

  ensure_supported_runtime()
  instructions = []

  for instruction in bytecodes:
    if isinstance(instruction, Instr) and isinstance(instruction.arg, CodeType):
      instruction = instruction.copy()
      instruction.arg = _set_code_filename(instruction.arg, filename)

    instructions.append(instruction)

  if not instructions or not isinstance(instructions[0], Instr) or instructions[0].name != "RESUME":
    instructions.insert(0, Instr("RESUME", 0, lineno=1))

  # Every reachable fallthrough must return; ordinary code does not receive
  # a scope-optimization flag simply because it has been compiled.
  if not isinstance(instructions[-1], Instr) or not instructions[-1].is_final():
    instructions.extend([
      Instr("LOAD_CONST", None),
      Instr("RETURN_VALUE"),
    ])

  compiled_bytecode = Bytecode(instructions)
  compiled_bytecode.filename = filename
  compiled_bytecode.name = name
  compiled_bytecode.qualname = name
  compiled_bytecode.first_lineno = 1

  return compiled_bytecode
