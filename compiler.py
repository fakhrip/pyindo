from types import CodeType
from typing import Tuple
from bytecode import Compare, Instr, Bytecode, Label


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
        case "+":
            bytecodes.append(Instr("BINARY_ADD"))
        case "-":
            bytecodes.append(Instr("BINARY_SUBTRACT"))
        case "/":
            bytecodes.append(Instr("BINARY_TRUE_DIVIDE"))
        case "*":
            bytecodes.append(Instr("BINARY_MULTIPLY"))
        case "*":
            bytecodes.append(Instr("BINARY_MULTIPLY"))
        case "&":
            bytecodes.append(Instr("BINARY_AND"))
        case "%":
            bytecodes.append(Instr("BINARY_MODULO"))
        case "|":
            bytecodes.append(Instr("BINARY_OR"))
        case "<<":
            bytecodes.append(Instr("BINARY_LSHIFT"))
        case ">>":
            bytecodes.append(Instr("BINARY_RSHIFT"))
        case "**":
            bytecodes.append(Instr("BINARY_POWER"))

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


def format_print(args: list, line_number: int, is_global_scope: bool) -> list:
    bytecodes = []

    bytecodes.append(
        Instr(
            "LOAD_NAME" if is_global_scope else "LOAD_GLOBAL",
            "print",
            lineno=line_number,
        )
    )

    for arg in args:
        match arg:
            case (v_value, v_type) if v_type == str:
                bytecodes.append(Instr("LOAD_CONST", v_value))
            case [_]:
                bytecodes.extend(arg)
                bytecodes.append(Instr("FORMAT_VALUE", 0))

    bytecodes.extend(
        [
            Instr("BUILD_STRING", len(args)),
            Instr("LOAD_CONST", ""),
            Instr("LOAD_CONST", ("end",)),
            Instr("CALL_FUNCTION_KW", 2),
            Instr("POP_TOP"),
            Instr("LOAD_CONST", None),
            Instr("RETURN_VALUE"),
        ]
    )

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
            Instr("LOAD_CONST", None),  # TODO: Add function return value
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
        label_else = Label()
        bytecodes.extend(
            [
                *function_bytecodes["header"],
                Instr("POP_JUMP_IF_FALSE", label_else),
                *function_bytecodes["content"],
                label_else,
                Instr("LOAD_CONST", None),
                Instr("RETURN_VALUE"),
            ]
        )
    else:
        # Function content definition for other functions
        if function_name:
            # Not an anonymous function so need to compile the function and
            # store its identifier in the bytecode
            compiled_bytecode = compile_bytecodes(function_bytecodes["content"])
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


def define_function_header(
    function_name: str,
    function_params: list,
    is_entrypoint_function: bool,
    line_number: int,
) -> list:
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

    return bytecodes


def compile_bytecodes(bytecodes: list) -> Bytecode:
    return Bytecode(bytecodes)
