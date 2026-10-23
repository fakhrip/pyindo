from types import CodeType
from typing import Tuple, Union
from bytecode import BinaryOp, Compare, Instr, Bytecode, Label

from pyindo.types import LiteralString
from pyindo.runtime import ensure_supported_runtime

import re
import codecs


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
    bytecodes = []

    match c_type:
        case "selainnya":
            bytecodes.extend(statements)
        case "selainnya jika" | "jika":
            bytecodes.extend(expressions)

            if condition_label:
                bytecodes.append(Instr("POP_JUMP_IF_FALSE", condition_label))

            bytecodes.extend(statements)

            if jump_label:
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
    bytecodes = []

    match function_name:
        case "tampilkan":
            bytecodes = format_print(function_params, line_number, is_global_scope)
            return bytecodes

    bytecodes.append(Instr("LOAD_NAME", function_name))

    if len(function_params) > 0:
        bytecodes.extend(
            [
                # TODO:
                # Add function params bytecode to the function call
                # if there are any
            ]
        )

    bytecodes.extend(
        [
            Instr("CALL_FUNCTION", 0),
            Instr("POP_TOP"),
            Instr("LOAD_CONST", None),
            Instr("RETURN_VALUE"),
        ]
    )

    return bytecodes


def define_function_content(
    function_name: str,
    function_bytecodes: dict,
    is_entrypoint_function: bool,
    line_number: int,
) -> Tuple[list, CodeType]:
    bytecodes = []
    bytecode_codechunk = None

    if is_entrypoint_function:
        # Function content definition for entrypoint
        tail_bytecodes, tail_label = function_bytecodes["tail"]
        bytecodes.extend(
            [
                *function_bytecodes["header"],
                Instr("POP_JUMP_IF_FALSE", tail_label),
                *function_bytecodes["content"],
            ]
        )

        if len(function_bytecodes["content"]) > 0 and isinstance(
            function_bytecodes["content"][-1], Label
        ):
            bytecodes.extend(tail_bytecodes[1:])

        bytecodes.extend(tail_bytecodes)
    else:
        # Function content definition for other functions
        if function_name:
            # Not an anonymous function so need to compile the function and
            # store its identifier in the bytecode
            compiled_bytecode = compile_bytecodes(
                [*function_bytecodes["content"], *function_bytecodes["tail"][0]]
            )
            bytecode_codechunk = compiled_bytecode.to_code()

            bytecodes.extend(
                [
                    *function_bytecodes["header"],
                    Instr("LOAD_CONST", bytecode_codechunk),
                    Instr("LOAD_CONST", function_name),
                    Instr(
                        "MAKE_FUNCTION",
                        4 if len(function_bytecodes["header"]) > 0 else 0,
                    ),
                    Instr("STORE_NAME", function_name),
                ]
            )
        else:
            # This is an anonymous function which means that we dont have to
            # compile the function and store its identifier in the bytecode
            bytecodes.extend(
                [
                    *function_bytecodes["header"],
                    *function_bytecodes["content"],
                ]
            )

    return (bytecodes, bytecode_codechunk)


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
  instructions = list(bytecodes)

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
